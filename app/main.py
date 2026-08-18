"""
FastAPI Backend Application for ConsultBae AI Automation Platform.
Serves Web App UI, Audio Upload & Processing Pipeline, Candidate Database, and n8n API Integrations.
"""

import os
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline.cleaner import normalize_phone, normalize_name, normalize_email, normalize_skills
from pipeline.db import (
    get_db_connection,
    init_db,
    save_audio_submission,
    get_all_audio_submissions,
    get_all_unified_candidates,
    find_candidate_by_phone_or_email,
    save_unified_candidate,
    update_unified_candidate,
    DEFAULT_DB_PATH,
)
from pipeline.models import AudioSubmission, UnifiedCandidate
from pipeline.ingest import run_ingestion_pipeline
from .audio_analyzer import analyze_audio_file

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
UPLOADS_DIR = APP_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Ensure DB is initialized
init_db(DEFAULT_DB_PATH)

app = FastAPI(
    title="ConsultBae AI Automation Platform",
    description="Unified Candidate Pipeline, n8n Integrations, and Audio Signal Processing Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount Static Files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Pydantic Schemas
class DuplicateCheckRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None


class CandidateEnrichRequest(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = "Unknown"
    skills: List[str] = []
    experience_years: Optional[float] = 0.0
    current_ctc_lpa: Optional[float] = 0.0
    primary_category: Optional[str] = "automation-heavy"
    seniority_level: Optional[str] = "Mid-Level"
    ai_notes: Optional[str] = ""
    source: Optional[str] = "n8n_automation"


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serves the main single page web application."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>ConsultBae AI Automation API Running. Static UI not yet mounted.</h1>"


# --------------------------------------------------------------------------
# AUDIO APP ENDPOINTS (TASK 3)
# --------------------------------------------------------------------------

@app.post("/api/audio/submit")
async def submit_audio(
    worker_name: str = Form(...),
    phone: str = Form(...),
    audio_file: UploadFile = File(...)
):
    """
    Ingests an audio recording (mic or file upload), extracts signal properties,
    links or creates a candidate profile in SQLite, and persists the submission.
    """
    clean_name = normalize_name(worker_name)
    clean_phone = normalize_phone(phone)

    if not clean_name or clean_name == "Unknown":
        raise HTTPException(status_code=400, detail="Please enter a valid worker name.")
    if not clean_phone:
        raise HTTPException(status_code=400, detail="Please enter a valid 10-digit phone number.")

    # Generate unique filename preserving extension
    ext = Path(audio_file.filename or "recording.wav").suffix.lower()
    if not ext:
        ext = ".wav" if "wav" in (audio_file.content_type or "") else ".webm"

    unique_filename = f"{uuid.uuid4().hex[:12]}_{clean_phone}{ext}"
    saved_filepath = UPLOADS_DIR / unique_filename

    # Save uploaded bytes
    content = await audio_file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    with open(saved_filepath, "wb") as f:
        f.write(content)

    # Extract audio signal properties
    audio_props = analyze_audio_file(saved_filepath)

    # Link to Unified Candidate in database
    matched_candidate = find_candidate_by_phone_or_email(phone=clean_phone, name=clean_name)
    candidate_id = None

    if matched_candidate:
        candidate_id = matched_candidate["id"]
    else:
        # Create a new candidate record for this gig worker
        new_cand = UnifiedCandidate(
            full_name=clean_name,
            phone=clean_phone,
            city="Unknown",
            status="Active",
            source_count=1,
            sources_merged=["gig_audio_submission"],
        )
        candidate_id = save_unified_candidate(new_cand)

    # Create and save AudioSubmission record
    sub = AudioSubmission(
        candidate_id=candidate_id,
        worker_name=clean_name,
        phone=clean_phone,
        audio_filename=unique_filename,
        audio_filepath=str(saved_filepath),
        file_size_bytes=audio_props["file_size_bytes"],
        duration_seconds=audio_props["duration_seconds"],
        sample_rate_khz=audio_props["sample_rate_khz"],
        bitrate_kbps=audio_props["bitrate_kbps"],
        loudness_dbfs=audio_props["loudness_dbfs"],
        snr_db=audio_props.get("snr_db"),
        noise_floor_dbfs=audio_props.get("noise_floor_dbfs"),
        clipping_ratio=audio_props.get("clipping_ratio", 0.0),
        quality_verdict=audio_props["quality_verdict"],
        quality_notes=audio_props.get("quality_notes", ""),
    )

    sub_id = save_audio_submission(sub)
    sub.id = sub_id

    return {
        "status": "SUCCESS",
        "message": "Audio recording successfully analyzed and stored.",
        "submission": {
            "id": sub_id,
            "candidate_id": candidate_id,
            "worker_name": clean_name,
            "phone": clean_phone,
            "filename": unique_filename,
            "playback_url": f"/api/audio/stream/{unique_filename}",
            "file_size_bytes": sub.file_size_bytes,
            "duration_seconds": sub.duration_seconds,
            "sample_rate_khz": sub.sample_rate_khz,
            "bitrate_kbps": sub.bitrate_kbps,
            "loudness_dbfs": sub.loudness_dbfs,
            "snr_db": sub.snr_db,
            "noise_floor_dbfs": sub.noise_floor_dbfs,
            "clipping_ratio": sub.clipping_ratio,
            "quality_verdict": sub.quality_verdict,
            "quality_notes": sub.quality_notes,
            "submitted_at": sub.submitted_at,
        }
    }


@app.get("/api/audio/submissions")
async def list_audio_submissions():
    """Returns all recorded audio submissions with playback URLs."""
    submissions = get_all_audio_submissions()
    for s in submissions:
        s["playback_url"] = f"/api/audio/stream/{s['audio_filename']}"
    return {"count": len(submissions), "submissions": submissions}


@app.get("/api/audio/stream/{filename}")
async def stream_audio(filename: str):
    """Streams the audio file for in-browser playback."""
    file_path = UPLOADS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found.")

    ext = file_path.suffix.lower()
    media_type = "audio/wav"
    if ext == ".mp3":
        media_type = "audio/mpeg"
    elif ext == ".webm":
        media_type = "audio/webm"
    elif ext == ".ogg":
        media_type = "audio/ogg"
    elif ext == ".m4a":
        media_type = "audio/mp4"

    return FileResponse(path=str(file_path), media_type=media_type, filename=filename)


# --------------------------------------------------------------------------
# CANDIDATES & DATABASE ENDPOINTS (TASK 1 & 2)
# --------------------------------------------------------------------------

@app.get("/api/candidates")
async def get_candidates(q: Optional[str] = Query(None, description="Search query")):
    """Returns unified candidate records from Task 1 with optional filtering."""
    candidates = get_all_unified_candidates()
    if q:
        query_lower = q.lower()
        candidates = [
            c for c in candidates
            if query_lower in c["full_name"].lower()
            or (c["email"] and query_lower in c["email"].lower())
            or (c["phone"] and query_lower in c["phone"])
            or query_lower in c["city"].lower()
            or any(query_lower in s.lower() for s in c["skills"])
        ]
    return {"count": len(candidates), "candidates": candidates}


@app.post("/api/candidates/check-duplicate")
async def check_candidate_duplicate(req: DuplicateCheckRequest):
    """
    Duplicate checking endpoint for n8n workflow.
    Returns whether a candidate matching phone, email, or name already exists in SQLite.
    """
    clean_phone = normalize_phone(req.phone) if req.phone else None
    clean_email = normalize_email(req.email) if req.email else None
    clean_name = normalize_name(req.name) if req.name else None

    matched = find_candidate_by_phone_or_email(phone=clean_phone, email=clean_email, name=clean_name)
    if matched:
        return {
            "is_duplicate": True,
            "message": f"Duplicate candidate found matching ID #{matched['id']}",
            "matched_candidate": matched,
        }
    return {
        "is_duplicate": False,
        "message": "Candidate is unique. No duplicates found in database.",
        "matched_candidate": None,
    }


@app.post("/api/candidates/enrich")
async def enrich_candidate(req: CandidateEnrichRequest):
    """
    Enriches or inserts a candidate with AI-classified skills and tags (for n8n writeback).
    """
    clean_phone = normalize_phone(req.phone) if req.phone else None
    clean_email = normalize_email(req.email) if req.email else None
    clean_name = normalize_name(req.full_name)
    skills = normalize_skills(req.skills)

    matched = find_candidate_by_phone_or_email(phone=clean_phone, email=clean_email, name=clean_name)

    if matched:
        # Update existing
        cand_obj = UnifiedCandidate(
            id=matched["id"],
            full_name=clean_name if clean_name != "Unknown" else matched["full_name"],
            email=clean_email or matched["email"],
            phone=clean_phone or matched["phone"],
            city=req.city if req.city != "Unknown" else matched["city"],
            skills=sorted(list(set(matched["skills"] + skills))),
            experience_years=req.experience_years or matched["experience_years"],
            current_ctc_lpa=req.current_ctc_lpa or matched["current_ctc_lpa"],
            current_ctc_raw_inr=matched["current_ctc_raw_inr"],
            hourly_rate_inr=matched["hourly_rate_inr"],
            monthly_rate_inr=matched["monthly_rate_inr"],
            status=matched["status"],
            verified=matched["verified"],
            projects_completed=matched["projects_completed"],
            applied_date=matched["applied_date"],
            source_count=len(set(matched["sources_merged"] + [req.source or "n8n_automation"])),
            sources_merged=list(set(matched["sources_merged"] + [req.source or "n8n_automation"])),
        )
        update_unified_candidate(cand_obj)
        return {"status": "UPDATED", "candidate": cand_obj}
    else:
        # Create new
        cand_obj = UnifiedCandidate(
            full_name=clean_name,
            email=clean_email,
            phone=clean_phone,
            city=req.city or "Unknown",
            skills=skills,
            experience_years=req.experience_years,
            current_ctc_lpa=req.current_ctc_lpa,
            status="Active",
            source_count=1,
            sources_merged=[req.source or "n8n_automation"],
        )
        new_id = save_unified_candidate(cand_obj)
        cand_obj.id = new_id
        return {"status": "CREATED", "candidate": cand_obj}


@app.post("/api/pipeline/run")
async def trigger_pipeline_run():
    """Triggers a fresh run of the Task 1 ingestion pipeline."""
    metrics = run_ingestion_pipeline(DEFAULT_DB_PATH, verbose=False)
    return {"status": "SUCCESS", "metrics": metrics}
