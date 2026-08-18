"""
Data models and dataclasses for ConsultBae Unified Database.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class SourceRecord:
    """Represents an unmerged individual record from a specific data source."""
    source_name: str  # 'source1_naukri', 'source2_gig_workers', 'source3_cbnexus'
    original_row_idx: int
    raw_data: Dict[str, Any]
    normalized_name: str
    normalized_email: Optional[str] = None
    normalized_phone: Optional[str] = None
    normalized_city: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    experience_years: Optional[float] = None
    ctc_lpa: Optional[float] = None
    ctc_raw_inr: Optional[int] = None
    rate_type: Optional[str] = None
    rate_amount: Optional[float] = None
    monthly_rate_inr: Optional[float] = None
    status: Optional[str] = None
    verified: Optional[bool] = None
    projects_completed: Optional[int] = None
    applied_date: Optional[str] = None
    issues_found: List[str] = field(default_factory=list)


@dataclass
class UnifiedCandidate:
    """Represents a unified, deduplicated master candidate record."""
    id: Optional[int] = None
    full_name: str = "Unknown"
    email: Optional[str] = None
    phone: Optional[str] = None
    city: str = "Unknown"
    skills: List[str] = field(default_factory=list)
    experience_years: Optional[float] = None
    current_ctc_lpa: Optional[float] = None
    current_ctc_raw_inr: Optional[int] = None
    hourly_rate_inr: Optional[float] = None
    monthly_rate_inr: Optional[float] = None
    status: Optional[str] = None
    verified: Optional[bool] = None
    projects_completed: Optional[int] = None
    applied_date: Optional[str] = None
    source_count: int = 0
    sources_merged: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class AudioSubmission:
    """Represents an audio recording submission from a gig worker."""
    id: Optional[int] = None
    candidate_id: Optional[int] = None
    worker_name: str = ""
    phone: str = ""
    audio_filename: str = ""
    audio_filepath: str = ""
    file_size_bytes: int = 0
    duration_seconds: float = 0.0
    sample_rate_khz: float = 0.0
    bitrate_kbps: float = 0.0
    loudness_dbfs: float = 0.0
    snr_db: Optional[float] = None
    noise_floor_dbfs: Optional[float] = None
    clipping_ratio: float = 0.0
    quality_verdict: str = "Unknown"
    quality_notes: str = ""
    submitted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
