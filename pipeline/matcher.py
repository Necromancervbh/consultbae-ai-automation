"""
Entity Resolution and Multi-Source Merging Engine.
Implements a deterministic matching graph across Phone, Email, and Name+City heuristics.
"""

from typing import List, Dict, Optional, Tuple, Any
from .models import SourceRecord, UnifiedCandidate


class EntityResolver:
    """
    Manages identity resolution and incremental profile unification.
    Maintains index lookup tables for fast, collision-free candidate matching.
    """

    def __init__(self):
        self.candidates: List[UnifiedCandidate] = []
        self.email_to_candidate_idx: Dict[str, int] = {}
        self.phone_to_candidate_idx: Dict[str, int] = {}
        self.name_city_to_candidate_idx: Dict[Tuple[str, str], int] = {}
        self.source_records_by_candidate: Dict[int, List[SourceRecord]] = {}
        self.merge_logs: List[Dict[str, Any]] = []

    def _is_more_complete_name(self, new_name: str, existing_name: str) -> bool:
        """
        Determines if new_name is more informative than existing_name.
        e.g., 'Rohit Verma' is more complete than 'R. Verma' or 'Unknown'.
        """
        if existing_name in ("Unknown", ""):
            return True
        if "." in existing_name and "." not in new_name and len(new_name) > len(existing_name):
            return True
        return False

    def find_match_index(self, record: SourceRecord) -> Optional[int]:
        """
        Finds candidate index by checking identifiers in priority order:
        1. Exact match on normalized Email
        2. Exact match on normalized Phone
        3. Match on (Name + City) ONLY if neither email nor phone contradicts existing candidate
        """
        # Step 1: Check Email
        if record.normalized_email and record.normalized_email in self.email_to_candidate_idx:
            return self.email_to_candidate_idx[record.normalized_email]

        # Step 2: Check Phone
        if record.normalized_phone and record.normalized_phone in self.phone_to_candidate_idx:
            return self.phone_to_candidate_idx[record.normalized_phone]

        # Step 3: Check Name + City fallback
        if record.normalized_name and record.normalized_name != "Unknown" and record.normalized_city:
            key = (record.normalized_name.lower(), record.normalized_city.lower())
            if key in self.name_city_to_candidate_idx:
                candidate_idx = self.name_city_to_candidate_idx[key]
                candidate = self.candidates[candidate_idx]

                # Conflict Safety Check:
                # If record has email and candidate already has a DIFFERENT email -> DO NOT merge
                if record.normalized_email and candidate.email and record.normalized_email != candidate.email:
                    return None

                # If record has phone and candidate already has a DIFFERENT phone -> DO NOT merge
                if record.normalized_phone and candidate.phone and record.normalized_phone != candidate.phone:
                    return None

                return candidate_idx

        return None

    def merge_record(self, record: SourceRecord) -> int:
        """
        Merges a source record into an existing unified candidate or creates a new candidate.
        Returns the index of the unified candidate.
        """
        matched_idx = self.find_match_index(record)

        if matched_idx is not None:
            # Merge into existing candidate
            cand = self.candidates[matched_idx]
            merge_reasons = []

            # 1. Update Name if more complete
            if self._is_more_complete_name(record.normalized_name, cand.full_name):
                merge_reasons.append(f"Updated name from '{cand.full_name}' to '{record.normalized_name}'")
                cand.full_name = record.normalized_name

            # 2. Update Email if not set
            if not cand.email and record.normalized_email:
                cand.email = record.normalized_email
                self.email_to_candidate_idx[cand.email] = matched_idx
                merge_reasons.append(f"Added email '{cand.email}'")

            # 3. Update Phone if not set
            if not cand.phone and record.normalized_phone:
                cand.phone = record.normalized_phone
                self.phone_to_candidate_idx[cand.phone] = matched_idx
                merge_reasons.append(f"Added phone '{cand.phone}'")

            # 4. Update City if not set or more specific
            if (cand.city == "Unknown" or not cand.city) and record.normalized_city:
                cand.city = record.normalized_city

            # 5. Union of Skills (deduplicated)
            if record.skills:
                existing_lower = {s.lower() for s in cand.skills}
                for s in record.skills:
                    if s.lower() not in existing_lower:
                        cand.skills.append(s)
                        existing_lower.add(s.lower())
                cand.skills.sort()

            # 6. Experience
            if cand.experience_years is None and record.experience_years is not None:
                cand.experience_years = record.experience_years

            # 7. CTC (Naukri)
            if cand.current_ctc_lpa is None and record.ctc_lpa is not None:
                cand.current_ctc_lpa = record.ctc_lpa
                cand.current_ctc_raw_inr = record.ctc_raw_inr

            # 8. Rates (Gig Workers)
            if cand.hourly_rate_inr is None and record.rate_type == "hourly":
                cand.hourly_rate_inr = record.rate_amount
            if cand.monthly_rate_inr is None and record.monthly_rate_inr is not None:
                cand.monthly_rate_inr = record.monthly_rate_inr

            # 9. Status & Verification & Projects
            if cand.status is None or cand.status == "Unknown":
                cand.status = record.status or "Active"
            elif record.status and record.status != "Unknown":
                cand.status = record.status

            if cand.verified is None and record.verified is not None:
                cand.verified = record.verified

            if record.projects_completed is not None:
                cand.projects_completed = max(cand.projects_completed or 0, record.projects_completed)

            if not cand.applied_date and record.applied_date:
                cand.applied_date = record.applied_date

            # Provenance tracking
            if record.source_name not in cand.sources_merged:
                cand.sources_merged.append(record.source_name)
            cand.source_count = len(cand.sources_merged)

            self.source_records_by_candidate[matched_idx].append(record)
            self.merge_logs.append({
                "action": "MERGED_INTO_EXISTING",
                "candidate_idx": matched_idx,
                "candidate_name": cand.full_name,
                "source_name": record.source_name,
                "reasons": merge_reasons,
            })
            return matched_idx

        else:
            # Create new UnifiedCandidate
            new_cand_idx = len(self.candidates)
            new_cand = UnifiedCandidate(
                full_name=record.normalized_name,
                email=record.normalized_email,
                phone=record.normalized_phone,
                city=record.normalized_city or "Unknown",
                skills=list(record.skills),
                experience_years=record.experience_years,
                current_ctc_lpa=record.ctc_lpa,
                current_ctc_raw_inr=record.ctc_raw_inr,
                hourly_rate_inr=record.rate_amount if record.rate_type == "hourly" else None,
                monthly_rate_inr=record.monthly_rate_inr,
                status=record.status or "Active",
                verified=record.verified,
                projects_completed=record.projects_completed or 0,
                applied_date=record.applied_date,
                source_count=1,
                sources_merged=[record.source_name],
            )
            self.candidates.append(new_cand)
            self.source_records_by_candidate[new_cand_idx] = [record]

            # Index lookups
            if new_cand.email:
                self.email_to_candidate_idx[new_cand.email] = new_cand_idx
            if new_cand.phone:
                self.phone_to_candidate_idx[new_cand.phone] = new_cand_idx
            if new_cand.full_name and new_cand.full_name != "Unknown" and new_cand.city:
                self.name_city_to_candidate_idx[(new_cand.full_name.lower(), new_cand.city.lower())] = new_cand_idx

            self.merge_logs.append({
                "action": "CREATED_NEW_CANDIDATE",
                "candidate_idx": new_cand_idx,
                "candidate_name": new_cand.full_name,
                "source_name": record.source_name,
            })
            return new_cand_idx
