"""
n8n Workflow Local Simulation Runner (Task 2).
Demonstrates the exact end-to-end logic of the n8n low-code workflow:
1. Webhook Payload Ingestion
2. Data Cleaning & Phone/Email Normalization
3. Database Duplicate Query
4. Duplicate Alert Dispatch (if duplicate exists)
5. AI / LLM Skill Auto-Classification (if new candidate)
6. Writeback to Unified Database
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from pipeline.cleaner import normalize_phone, normalize_email, normalize_name, normalize_skills
from pipeline.db import find_candidate_by_phone_or_email, save_unified_candidate, get_all_unified_candidates
from pipeline.models import UnifiedCandidate


def classify_skills_ai(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulates the n8n LLM Node for automated skill classification.
    """
    skills = candidate.get("skills", [])
    skills_lower = [s.lower() for s in skills]

    auto_keywords = ['n8n', 'zapier', 'selenium', 'langchain', 'rest apis', 'web scraping']
    web_keywords = ['react', 'javascript', 'fastapi', 'nodejs', 'html', 'css']
    data_keywords = ['pandas', 'sql', 'mysql', 'mongodb', 'postgresql', 'data']

    auto_score = sum(1 for s in skills_lower if any(k in s for k in auto_keywords))
    web_score = sum(1 for s in skills_lower if any(k in s for k in web_keywords))
    data_score = sum(1 for s in skills_lower if any(k in s for k in data_keywords))

    if auto_score >= web_score and auto_score >= data_score and auto_score > 0:
        category = "automation-heavy"
        tags = ["workflow-orchestration", "rpa-ai"]
        reasoning = f"Candidate excels in automation tooling: {', '.join(skills)}"
    elif web_score >= data_score and web_score > 0:
        category = "web dev"
        tags = ["frontend-backend", "fullstack"]
        reasoning = f"Strong web engineering capabilities: {', '.join(skills)}"
    elif data_score > 0:
        category = "data"
        tags = ["data-engineering", "database-design"]
        reasoning = f"Data manipulation and database focus: {', '.join(skills)}"
    else:
        category = "general-it"
        tags = ["it-support"]
        reasoning = "Broad general technology skill set."

    exp = candidate.get("experience_years", 0)
    seniority = "Senior" if exp >= 4.0 else ("Junior / Associate" if exp <= 1.5 else "Mid-Level")

    return {
        "primary_category": category,
        "secondary_tags": tags,
        "seniority_level": seniority,
        "confidence_score": 0.96,
        "reasoning": reasoning
    }


def execute_n8n_pipeline(incoming_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the step-by-step logic of the n8n pipeline.
    """
    print("\n" + "=" * 65)
    print(f" [n8n FLOW EXECUTION] Processing Candidate: {incoming_payload.get('name') or incoming_payload.get('full_name')}")
    print("=" * 65)

    # Node 1: Webhook Ingest
    print(">> [Step 1: Webhook Trigger] Received raw JSON payload:")
    print(" ", json.dumps(incoming_payload))

    # Node 2: Data Cleaning
    norm_phone = normalize_phone(incoming_payload.get("phone") or incoming_payload.get("Phone"))
    norm_email = normalize_email(incoming_payload.get("email") or incoming_payload.get("Email"))
    norm_name = normalize_name(incoming_payload.get("name") or incoming_payload.get("full_name"))
    skills = normalize_skills(incoming_payload.get("skills") or incoming_payload.get("skill_tags") or [])

    cleaned = {
        "full_name": norm_name,
        "email": norm_email,
        "phone": norm_phone,
        "city": incoming_payload.get("city", "Unknown"),
        "skills": skills,
        "experience_years": float(incoming_payload.get("experience_years", 2.5)),
        "current_ctc_lpa": float(incoming_payload.get("current_ctc_lpa", 6.0)),
    }
    print(f">> [Step 2: Clean & Normalize] Standardized Phone: {norm_phone} | Email: {norm_email}")

    # Node 3: Database Check
    matched_candidate = find_candidate_by_phone_or_email(phone=norm_phone, email=norm_email)

    if matched_candidate:
        # Branch A: Duplicate detected
        print(">> [Step 3: Database Duplicate Check] DUPLICATE FOUND!")
        print(f"   Matched existing Candidate ID #{matched_candidate['id']} ({matched_candidate['full_name']})")
        print(f"   Sources already merged: {matched_candidate['sources_merged']}")

        alert_payload = {
            "alert_type": "DUPLICATE_CANDIDATE_DETECTED",
            "candidate_name": norm_name,
            "email": norm_email,
            "phone": norm_phone,
            "matched_candidate_id": matched_candidate["id"],
            "matched_candidate_sources": matched_candidate["sources_merged"],
            "action_taken": "Sent alert to Slack #recruitment-alerts; skipped duplicate creation.",
        }
        print(">> [Step 4: Send Duplicate Alert] Dispatched notification payload:")
        print(" ", json.dumps(alert_payload, indent=2))
        return {"status": "DUPLICATE_ALERT_SENT", "data": alert_payload}

    else:
        # Branch B: New candidate
        print(">> [Step 3: Database Duplicate Check] No duplicate found. Proceeding with new profile.")

        # Node 5: LLM Skill Classifier
        classification = classify_skills_ai(cleaned)
        print(f">> [Step 4: LLM AI Classifier] Category: '{classification['primary_category']}' ({classification['seniority_level']})")
        print(f"   Reasoning: {classification['reasoning']}")

        # Node 6: Writeback to DB
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
        print(f">> [Step 5: Database Writeback] Inserted enriched candidate into SQLite (ID: #{new_id})")

        return {
            "status": "ENRICHED_AND_SAVED",
            "candidate_id": new_id,
            "candidate_name": norm_name,
            "classification": classification,
        }


def main():
    print("Testing n8n Automation Workflow Simulation...\n")

    # Test Case 1: Ingesting an existing candidate (Tanvi Gupta) -> Should trigger duplicate alert
    dup_test = {
        "full_name": "Tanvi Gupta",
        "email": "tanvi.gupta31@example.com",
        "phone": "+919000000254",
        "skills": "n8n, Python, Docker",
        "experience_years": 4.2
    }
    execute_n8n_pipeline(dup_test)

    # Test Case 2: Ingesting a brand new candidate (Harsh Vardhan) -> Should classify and persist
    new_test = {
        "full_name": "Harsh Vardhan",
        "email": "harsh.vardhan@ai-consultbae.io",
        "phone": "+91-9876543210",
        "city": "Bengaluru",
        "skills": "n8n, LangChain, Zapier, Python, FastAPI, Web Scraping",
        "experience_years": 4.5,
        "current_ctc_lpa": 12.5
    }
    execute_n8n_pipeline(new_test)


if __name__ == "__main__":
    main()
