"""
n8n Workflow Local Simulation Runner (Task 2).
Demonstrates the exact end-to-end logic of the n8n low-code workflow:

  1. Webhook Payload Ingestion
  2. Data Cleaning & Phone/Email Normalization
  3. Database Duplicate Query
  4. Duplicate Alert Dispatch (if duplicate exists)
  5. AI / LLM Skill Auto-Classification (if new candidate)
     Priority order:
       1. Groq  (free, fast) — set GROQ_API_KEY in .env
       2. OpenAI (paid)      — set OPENAI_API_KEY in .env
       3. Rule-based fallback (no key needed, always works)
  6. Writeback to Unified Database

See .env.example for how to configure your preferred provider.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Load .env automatically if present (no error if file doesn't exist)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed — set env vars manually

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from pipeline.cleaner import normalize_phone, normalize_email, normalize_name, normalize_skills
from pipeline.db import find_candidate_by_phone_or_email, save_unified_candidate
from pipeline.models import UnifiedCandidate


# ─────────────────────────────────────────────────────────────────────────────
#  Provider Configuration (loaded from .env)
# ─────────────────────────────────────────────────────────────────────────────

GROQ_API_KEY:   Optional[str] = os.environ.get("GROQ_API_KEY",   "").strip() or None
GROQ_MODEL:     str           = os.environ.get("GROQ_MODEL",     "llama-3.3-70b-versatile")

GEMINI_API_KEY: Optional[str] = os.environ.get("GEMINI_API_KEY", "").strip() or None
GEMINI_MODEL:   str           = os.environ.get("GEMINI_MODEL",   "gemini-3.5-flash-lite")

OPENAI_API_KEY: Optional[str] = os.environ.get("OPENAI_API_KEY", "").strip() or None
OPENAI_MODEL:   str           = os.environ.get("OPENAI_MODEL",   "gpt-4o-mini")

# Active provider — first configured key wins
if GROQ_API_KEY:
    ACTIVE_PROVIDER = f"groq/{GROQ_MODEL}"
elif GEMINI_API_KEY:
    ACTIVE_PROVIDER = f"gemini/{GEMINI_MODEL}"
elif OPENAI_API_KEY:
    ACTIVE_PROVIDER = f"openai/{OPENAI_MODEL}"
else:
    ACTIVE_PROVIDER = "rule-based-fallback"

# Build clients eagerly so import errors surface at startup
_groq_client   = None
_gemini_client = None
_openai_client = None

if GROQ_API_KEY:
    try:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY)
    except ImportError:
        pass

if GEMINI_API_KEY and _groq_client is None:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_client = genai.GenerativeModel(GEMINI_MODEL)
    except ImportError:
        pass

if OPENAI_API_KEY and _groq_client is None and _gemini_client is None:
    try:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  Shared prompt (same for all providers)
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an expert technical recruiter AI specialising in the Indian gig/consulting market.
Given a candidate's skills list and years of experience, classify them and return ONLY a
valid JSON object with exactly these keys:

  primary_category  : one of "automation-heavy" | "web dev" | "data" | "general-it"
  secondary_tags    : array of 1-3 short lowercase tag strings (e.g. ["rpa-ai", "workflow-orchestration"])
  seniority_level   : one of "Junior / Associate" | "Mid-Level" | "Senior"
  confidence_score  : float between 0.0 and 1.0
  reasoning         : one sentence explaining the classification decision

Do NOT wrap the JSON in markdown fences. Output raw JSON only."""


def _build_user_message(candidate: Dict[str, Any]) -> str:
    skills_str = ", ".join(candidate.get("skills", [])) or "Not specified"
    exp = candidate.get("experience_years", 0)
    return f"Skills: {skills_str}\nYears of experience: {exp}\nClassify this candidate."


def _parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
    """Safely parse LLM output, stripping accidental markdown fences."""
    text = raw.strip()
    # Strip ```json ... ``` wrappers if model ignores instructions
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        result = json.loads(text)
        required = {"primary_category", "secondary_tags", "seniority_level",
                    "confidence_score", "reasoning"}
        return result if required.issubset(result.keys()) else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Provider 1 — Groq (free, fast LPU inference)
# ─────────────────────────────────────────────────────────────────────────────

def _classify_with_groq(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Calls Groq LLaMA inference API. Returns None on any error."""
    if _groq_client is None:
        return None
    try:
        response = _groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": _build_user_message(candidate)},
            ],
            temperature=0.2,
            max_tokens=300,
            timeout=15,
        )
        raw = response.choices[0].message.content
        result = _parse_llm_json(raw)
        if result:
            result["_classifier"] = f"groq/{GROQ_MODEL}"
        return result
    except Exception as exc:
        print(f"   [WARN] Groq call failed ({type(exc).__name__}: {exc}). Trying next provider.")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Provider 2 — Google Gemini (free, sign in with Google)
# ─────────────────────────────────────────────────────────────────────────────

def _classify_with_gemini(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Calls Google Gemini API. Returns None on any error."""
    if _gemini_client is None:
        return None
    try:
        # Gemini uses a single combined prompt (no system/user split in basic SDK)
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{_build_user_message(candidate)}"
        response = _gemini_client.generate_content(
            full_prompt,
            generation_config={"temperature": 0.2, "max_output_tokens": 300},
        )
        raw = response.text
        result = _parse_llm_json(raw)
        if result:
            result["_classifier"] = f"gemini/{GEMINI_MODEL}"
        return result
    except Exception as exc:
        print(f"   [WARN] Gemini call failed ({type(exc).__name__}: {exc}). Trying next provider.")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Provider 3 — OpenAI GPT (paid)
# ─────────────────────────────────────────────────────────────────────────────

def _classify_with_openai(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Calls OpenAI chat completions API. Returns None on any error."""
    if _openai_client is None:
        return None
    try:
        response = _openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": _build_user_message(candidate)},
            ],
            temperature=0.2,
            max_tokens=300,
            timeout=15,
        )
        raw = response.choices[0].message.content
        result = _parse_llm_json(raw)
        if result:
            result["_classifier"] = f"openai/{OPENAI_MODEL}"
        return result
    except Exception as exc:
        print(f"   [WARN] OpenAI call failed ({type(exc).__name__}: {exc}). Using rule-based fallback.")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Provider 3 — Rule-Based Fallback (zero dependencies, always works)
# ─────────────────────────────────────────────────────────────────────────────

def _classify_rule_based(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic keyword-scoring classifier. Mirrors the LLM output schema."""
    skills = candidate.get("skills", [])
    skills_lower = [s.lower() for s in skills]

    auto_keywords = ["n8n", "zapier", "selenium", "langchain", "rest apis",
                     "web scraping", "make", "rpa", "automation"]
    web_keywords  = ["react", "javascript", "fastapi", "node.js", "nodejs",
                     "html", "css", "typescript", "vue", "angular"]
    data_keywords = ["pandas", "sql", "mysql", "mongodb", "postgresql",
                     "spark", "dbt", "data", "numpy", "tableau"]

    auto_score = sum(1 for s in skills_lower if any(k in s for k in auto_keywords))
    web_score  = sum(1 for s in skills_lower if any(k in s for k in web_keywords))
    data_score = sum(1 for s in skills_lower if any(k in s for k in data_keywords))

    if auto_score >= web_score and auto_score >= data_score and auto_score > 0:
        category  = "automation-heavy"
        tags      = ["workflow-orchestration", "rpa-ai"]
        reasoning = f"Candidate excels in automation tooling: {', '.join(skills)}"
    elif web_score >= data_score and web_score > 0:
        category  = "web dev"
        tags      = ["frontend-backend", "fullstack"]
        reasoning = f"Strong web engineering capabilities: {', '.join(skills)}"
    elif data_score > 0:
        category  = "data"
        tags      = ["data-engineering", "database-design"]
        reasoning = f"Data manipulation and database focus: {', '.join(skills)}"
    else:
        category  = "general-it"
        tags      = ["it-support"]
        reasoning = "Broad general technology skill set."

    exp = candidate.get("experience_years", 0)
    seniority = (
        "Senior"             if exp >= 4.0 else
        "Junior / Associate" if exp <= 1.5 else
        "Mid-Level"
    )

    return {
        "primary_category": category,
        "secondary_tags":   tags,
        "seniority_level":  seniority,
        "confidence_score": 0.91,
        "reasoning":        reasoning,
        "_classifier":      "rule-based-fallback",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Public Entry-Point: classify_skills_ai()
# ─────────────────────────────────────────────────────────────────────────────

def classify_skills_ai(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classifies a candidate's skills using the best available provider:
      1. Groq   (free LLaMA)   if GROQ_API_KEY is set   -> console.groq.com
      2. Gemini (free)         if GEMINI_API_KEY is set -> aistudio.google.com
      3. OpenAI (GPT, paid)    if OPENAI_API_KEY is set -> platform.openai.com
      4. Rule-based fallback   (always works, no key needed)

    Returns a dict with keys:
      primary_category, secondary_tags, seniority_level,
      confidence_score, reasoning, _classifier
    """
    return (
        _classify_with_groq(candidate) or
        _classify_with_gemini(candidate) or
        _classify_with_openai(candidate) or
        _classify_rule_based(candidate)
    )


# ─────────────────────────────────────────────────────────────────────────────
#  n8n Pipeline Simulation
# ─────────────────────────────────────────────────────────────────────────────

def execute_n8n_pipeline(incoming_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the step-by-step logic of the n8n pipeline locally.
    Mirrors the exact node flow in automation/n8n_candidate_enrichment_pipeline.json.
    """
    name_display = incoming_payload.get("name") or incoming_payload.get("full_name", "Unknown")
    print("\n" + "=" * 65)
    print(f" [n8n FLOW] Processing: {name_display}")
    print("=" * 65)

    # Node 1: Webhook Trigger
    print(">> [Step 1: Webhook Trigger] Received raw JSON payload:")
    print("  ", json.dumps(incoming_payload))

    # Node 2: Data Cleaning
    norm_phone = normalize_phone(incoming_payload.get("phone") or incoming_payload.get("Phone"))
    norm_email = normalize_email(incoming_payload.get("email") or incoming_payload.get("Email"))
    norm_name  = normalize_name(incoming_payload.get("name") or incoming_payload.get("full_name"))
    skills     = normalize_skills(
        incoming_payload.get("skills") or incoming_payload.get("skill_tags") or []
    )
    cleaned = {
        "full_name":        norm_name,
        "email":            norm_email,
        "phone":            norm_phone,
        "city":             incoming_payload.get("city", "Unknown"),
        "skills":           skills,
        "experience_years": float(incoming_payload.get("experience_years", 2.5)),
        "current_ctc_lpa":  float(incoming_payload.get("current_ctc_lpa", 6.0)),
    }
    print(f">> [Step 2: Clean & Normalize] Phone: {norm_phone} | Email: {norm_email}")

    # Node 3: DB Duplicate Check
    matched_candidate = find_candidate_by_phone_or_email(phone=norm_phone, email=norm_email)

    if matched_candidate:
        # Branch A: Duplicate
        print(">> [Step 3: Duplicate Check] [DUPLICATE] DUPLICATE FOUND!")
        print(f"   Matched Candidate ID #{matched_candidate['id']} ({matched_candidate['full_name']})")
        print(f"   Sources already merged: {matched_candidate['sources_merged']}")

        alert = {
            "alert_type":                "DUPLICATE_CANDIDATE_DETECTED",
            "candidate_name":            norm_name,
            "email":                     norm_email,
            "phone":                     norm_phone,
            "matched_candidate_id":      matched_candidate["id"],
            "matched_candidate_sources": matched_candidate["sources_merged"],
            "action_taken":              "Sent alert to Slack #recruitment-alerts; skipped duplicate creation.",
        }
        print(">> [Step 4: Send Duplicate Alert] Dispatched notification payload:")
        print("  ", json.dumps(alert, indent=2))
        return {"status": "DUPLICATE_ALERT_SENT", "data": alert}

    else:
        # Branch B: New candidate
        print(">> [Step 3: Duplicate Check] [OK] No duplicate found. Proceeding.")

        # Node 4: AI Classifier
        t0 = time.time()
        classification = classify_skills_ai(cleaned)
        elapsed = round((time.time() - t0) * 1000)
        classifier_used = classification.pop("_classifier", "unknown")

        provider_label = "[Groq]" if "groq" in classifier_used else \
                         "[OpenAI]" if "openai" in classifier_used else \
                         "[Rule-Based Fallback]"
        print(f">> [Step 4: AI Classifier] {provider_label} [{elapsed}ms]")
        print(f"   Category  : {classification['primary_category']} ({classification['seniority_level']})")
        print(f"   Tags      : {classification['secondary_tags']}")
        print(f"   Confidence: {classification['confidence_score']}")
        print(f"   Reasoning : {classification['reasoning']}")

        # Node 5: DB Writeback
        cand_obj = UnifiedCandidate(
            full_name=norm_name,
            email=norm_email,
            phone=norm_phone,
            city=cleaned["city"],
            skills=skills,
            experience_years=cleaned["experience_years"],
            current_ctc_lpa=cleaned["current_ctc_lpa"],
            status="Active",
            source_count=1,
            sources_merged=["n8n_webhook_ingest"],
        )
        new_id = save_unified_candidate(cand_obj)
        print(f">> [Step 5: DB Writeback] [OK] Inserted enriched candidate (ID: #{new_id})")

        return {
            "status":          "ENRICHED_AND_SAVED",
            "candidate_id":    new_id,
            "candidate_name":  norm_name,
            "classifier_used": classifier_used,
            "classification":  classification,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  CLI Entry-Point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if GROQ_API_KEY:
        mode = f"[Groq] {GROQ_MODEL} (FREE)"
    elif GEMINI_API_KEY:
        mode = f"[Gemini] {GEMINI_MODEL} (FREE)"
    elif OPENAI_API_KEY:
        mode = f"[OpenAI] {OPENAI_MODEL}"
    else:
        mode = "[Rule-Based Fallback] (no API key set)"

    print(f"\n  ConsultBae n8n Automation Simulation")
    print(f"  Classifier Mode : {mode}")
    print(f"  Tip: set GROQ_API_KEY or GEMINI_API_KEY in .env for free LLM mode.\n")

    # Test 1: Existing candidate -> duplicate alert
    execute_n8n_pipeline({
        "full_name":        "Tanvi Gupta",
        "email":            "tanvi.gupta31@example.com",
        "phone":            "+919000000254",
        "skills":           "n8n, Python, Docker",
        "experience_years": 4.2,
    })

    # Test 2: Brand new candidate -> classify & persist
    execute_n8n_pipeline({
        "full_name":        "Harsh Vardhan",
        "email":            "harsh.vardhan.new99@ai-consultbae.io",
        "phone":            "+91-9876543211",
        "city":             "Bengaluru",
        "skills":           "n8n, LangChain, Zapier, Python, FastAPI, Web Scraping",
        "experience_years": 4.5,
        "current_ctc_lpa":  12.5,
    })


if __name__ == "__main__":
    main()
