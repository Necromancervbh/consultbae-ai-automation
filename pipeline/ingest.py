"""
Ingestion Pipeline Script for ConsultBae Assignment (Task 1).
Parses 3 disparate data sources, resolves anomalies, deduplicates entities,
and populates the unified SQLite database.
"""

import csv
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple

from .cleaner import (
    normalize_phone,
    normalize_email,
    normalize_name,
    normalize_city,
    normalize_ctc,
    normalize_rate,
    normalize_date,
    normalize_verified,
    normalize_status,
    normalize_skills,
)
from .models import SourceRecord, UnifiedCandidate
from .matcher import EntityResolver
from .db import (
    init_db,
    save_unified_candidate,
    save_source_record,
    get_all_unified_candidates,
    DEFAULT_DB_PATH,
)

BASE_DIR = Path(__file__).resolve().parent.parent


def parse_source1_naukri(file_path: Path) -> List[SourceRecord]:
    """Parses source1_naukri_applicants.csv."""
    records = []
    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        for row_idx, row in enumerate(reader, start=2):
            if not row or not any(field.strip() for field in row):
                continue

            # Full Name,Email,Phone,City,Experience (Years),Current CTC,Applied Date,Skills
            full_name = row[0].strip() if len(row) > 0 else ""
            raw_email = row[1].strip() if len(row) > 1 else ""
            raw_phone = row[2].strip() if len(row) > 2 else ""
            raw_city = row[3].strip() if len(row) > 3 else ""
            raw_exp = row[4].strip() if len(row) > 4 else ""
            raw_ctc = row[5].strip() if len(row) > 5 else ""
            raw_date = row[6].strip() if len(row) > 6 else ""
            raw_skills = row[7].strip() if len(row) > 7 else ""

            issues = []

            # Clean name
            norm_name = normalize_name(full_name)
            if norm_name != full_name:
                issues.append(f"Name cleaned from '{full_name}' to '{norm_name}'")

            # Clean email
            norm_email = normalize_email(raw_email)
            if norm_email != raw_email:
                issues.append(f"Email normalized from '{raw_email}' to '{norm_email}'")

            # Clean phone
            norm_phone = normalize_phone(raw_phone)
            if norm_phone != raw_phone:
                issues.append(f"Phone formatted from '{raw_phone}' to '{norm_phone}'")

            # Clean city
            norm_city = normalize_city(raw_city)
            if norm_city != raw_city:
                issues.append(f"City standardized from '{raw_city}' to '{norm_city}'")

            # Experience
            try:
                exp_years = float(raw_exp) if raw_exp else None
            except ValueError:
                exp_years = None
                issues.append(f"Invalid experience string '{raw_exp}'")

            # CTC
            ctc_lpa, ctc_raw = normalize_ctc(raw_ctc)
            if raw_ctc and str(raw_ctc) != str(ctc_lpa):
                issues.append(f"CTC value '{raw_ctc}' standardized to {ctc_lpa} LPA ({ctc_raw} INR)")

            # Date
            norm_date = normalize_date(raw_date)
            if raw_date and norm_date != raw_date:
                issues.append(f"Date '{raw_date}' parsed to ISO format '{norm_date}'")

            # Skills
            skills_list = normalize_skills(raw_skills)

            raw_dict = {
                "Full Name": full_name,
                "Email": raw_email,
                "Phone": raw_phone,
                "City": raw_city,
                "Experience (Years)": raw_exp,
                "Current CTC": raw_ctc,
                "Applied Date": raw_date,
                "Skills": raw_skills,
            }

            rec = SourceRecord(
                source_name="source1_naukri",
                original_row_idx=row_idx,
                raw_data=raw_dict,
                normalized_name=norm_name,
                normalized_email=norm_email,
                normalized_phone=norm_phone,
                normalized_city=norm_city,
                skills=skills_list,
                experience_years=exp_years,
                ctc_lpa=ctc_lpa,
                ctc_raw_inr=ctc_raw,
                applied_date=norm_date,
                issues_found=issues,
            )
            records.append(rec)

    return records


def parse_source2_gig_workers(file_path: Path) -> List[SourceRecord]:
    """Parses source2_gig_workers.csv with shifted column recovery and empty row handling."""
    records = []
    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        for row_idx, row in enumerate(reader, start=2):
            # Check for empty rows like row 12: ,,,,,
            if not row or not any(field.strip() for field in row):
                continue

            raw_dict = {f"col_{i}": val for i, val in enumerate(row)}
            issues = []

            # Check for column shift anomaly (e.g. row 20: skills in column 0, email in column 1)
            col0 = row[0].strip() if len(row) > 0 else ""
            col1 = row[1].strip() if len(row) > 1 else ""

            if ("@" not in col0) and ("@" in col1):
                # Shift detected!
                raw_skills = col0
                raw_email = col1
                worker_name = row[2].strip() if len(row) > 2 else ""
                raw_rate = row[3].strip() if len(row) > 3 else ""
                raw_loc = row[4].strip() if len(row) > 4 else ""
                raw_status = row[5].strip() if len(row) > 5 else "Active"
                issues.append("CRITICAL: Detected shifted column format (skills placed in email field). Automatically realigned columns.")
            else:
                raw_email = col0
                worker_name = col1
                raw_rate = row[2].strip() if len(row) > 2 else ""
                raw_loc = row[3].strip() if len(row) > 3 else ""
                raw_status = row[4].strip() if len(row) > 4 else "Active"
                raw_skills = row[5].strip() if len(row) > 5 else ""

            norm_name = normalize_name(worker_name)
            norm_email = normalize_email(raw_email)
            if raw_email and raw_email.isupper():
                issues.append(f"Uppercase email '{raw_email}' normalized to lowercase '{norm_email}'")

            norm_city = normalize_city(raw_loc)
            rate_info = normalize_rate(raw_rate)
            norm_status = normalize_status(raw_status)
            skills_list = normalize_skills(raw_skills)

            raw_dict = {
                "email_id": raw_email,
                "worker_name": worker_name,
                "rate": raw_rate,
                "location": raw_loc,
                "status": raw_status,
                "skill_tags": raw_skills,
            }

            rec = SourceRecord(
                source_name="source2_gig_workers",
                original_row_idx=row_idx,
                raw_data=raw_dict,
                normalized_name=norm_name,
                normalized_email=norm_email,
                normalized_city=norm_city,
                skills=skills_list,
                rate_type=rate_info["rate_type"],
                rate_amount=rate_info["rate_amount"],
                monthly_rate_inr=rate_info["monthly_inr"],
                status=norm_status,
                issues_found=issues,
            )
            records.append(rec)

    return records


def parse_source3_cbnexus(file_path: Path) -> List[SourceRecord]:
    """Parses source3_cbnexus_contacts.csv with repeated header detection."""
    records = []
    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        for row_idx, row in enumerate(reader, start=2):
            if not row or not any(field.strip() for field in row):
                continue

            raw_name = row[0].strip() if len(row) > 0 else ""
            raw_phone = row[1].strip() if len(row) > 1 else ""
            raw_city = row[2].strip() if len(row) > 2 else ""
            raw_verified = row[3].strip() if len(row) > 3 else ""
            raw_proj = row[4].strip() if len(row) > 4 else ""

            # Check for repeated header in data (row 16)
            if raw_name.lower() == "name" and raw_phone.lower().startswith("phone"):
                continue

            issues = []

            norm_name = normalize_name(raw_name)
            if raw_name.isupper():
                issues.append(f"ALL-CAPS name '{raw_name}' normalized to Title Case '{norm_name}'")

            norm_phone = normalize_phone(raw_phone)
            if norm_phone != raw_phone:
                issues.append(f"Phone '{raw_phone}' normalized to 10-digit '{norm_phone}'")

            norm_city = normalize_city(raw_city)
            verified_bool = normalize_verified(raw_verified)
            if raw_verified not in ("True", "False"):
                issues.append(f"Verification string '{raw_verified}' normalized to boolean {verified_bool}")

            try:
                projects = int(raw_proj) if raw_proj else 0
            except ValueError:
                projects = 0
                issues.append(f"Invalid projects count '{raw_proj}' default to 0")

            raw_dict = {
                "Name": raw_name,
                "Phone Number": raw_phone,
                "City": raw_city,
                "Verified": raw_verified,
                "Projects Completed": raw_proj,
            }

            rec = SourceRecord(
                source_name="source3_cbnexus",
                original_row_idx=row_idx,
                raw_data=raw_dict,
                normalized_name=norm_name,
                normalized_phone=norm_phone,
                normalized_city=norm_city,
                verified=verified_bool,
                projects_completed=projects,
                issues_found=issues,
            )
            records.append(rec)

    return records


def run_ingestion_pipeline(db_path: Path = DEFAULT_DB_PATH, verbose: bool = True) -> Dict[str, Any]:
    """
    Executes end-to-end ingestion and entity resolution:
    1. Resets and initializes SQLite DB schema.
    2. Parses all 3 CSV source files.
    3. Executes deterministic identity resolution graph.
    4. Persists unified candidates and source records.
    5. Returns metrics and issue logs.
    """
    if db_path.exists():
        db_path.unlink()

    init_db(db_path)

    s1_path = BASE_DIR / "source1_naukri_applicants.csv"
    s2_path = BASE_DIR / "source2_gig_workers.csv"
    s3_path = BASE_DIR / "source3_cbnexus_contacts.csv"

    s1_records = parse_source1_naukri(s1_path)
    s2_records = parse_source2_gig_workers(s2_path)
    s3_records = parse_source3_cbnexus(s3_path)

    resolver = EntityResolver()

    # Step 1: Ingest Source 1 (Naukri: has both email & phone)
    for rec in s1_records:
        resolver.merge_record(rec)

    # Step 2: Ingest Source 2 (Gig Workers: has email + rate)
    for rec in s2_records:
        resolver.merge_record(rec)

    # Step 3: Ingest Source 3 (CBNexus: has phone + verification)
    for rec in s3_records:
        resolver.merge_record(rec)

    # Step 4: Persist to Database
    candidate_id_map = {}
    for idx, candidate in enumerate(resolver.candidates):
        cand_id = save_unified_candidate(candidate, db_path)
        candidate.id = cand_id
        candidate_id_map[idx] = cand_id

        # Save source provenance records
        for src_rec in resolver.source_records_by_candidate.get(idx, []):
            save_source_record(cand_id, src_rec, db_path)

    # Calculate summary metrics
    total_source_records = len(s1_records) + len(s2_records) + len(s3_records)
    total_unified = len(resolver.candidates)
    cross_source_merged = sum(1 for c in resolver.candidates if c.source_count > 1)
    three_sources_merged = sum(1 for c in resolver.candidates if c.source_count == 3)

    summary = {
        "source1_count": len(s1_records),
        "source2_count": len(s2_records),
        "source3_count": len(s3_records),
        "total_source_records": total_source_records,
        "unified_candidates_count": total_unified,
        "cross_source_merged": cross_source_merged,
        "three_sources_merged": three_sources_merged,
        "merge_logs_count": len(resolver.merge_logs),
    }

    if verbose:
        print("=" * 70)
        print(" CONSULTBAE AI AUTOMATION - TASK 1 INGESTION COMPLETE ")
        print("=" * 70)
        print(f" Source 1 (Naukri Applicants):  {len(s1_records)} parsed")
        print(f" Source 2 (Gig Workers):        {len(s2_records)} parsed")
        print(f" Source 3 (CBNexus Contacts):   {len(s3_records)} parsed")
        print(f" Total Raw Input Records:       {total_source_records}")
        print(f" Unified Master Candidates:     {total_unified}")
        print(f" Merged Across >= 2 Sources:    {cross_source_merged}")
        print(f" Merged Across All 3 Sources:   {three_sources_merged}")
        print(f" SQLite Database Stored at:     {db_path}")
        print("=" * 70)

    return summary


if __name__ == "__main__":
    run_ingestion_pipeline()
