"""
Full Automated Test Suite for ConsultBae Assignment.
Verifies Task 1 (Database Merge), Task 2 (n8n API & Classifier), and Task 3 (Audio Extraction & Endpoints).
"""

import os
import sys
import wave
import json
import unittest
from pathlib import Path
import numpy as np

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from pipeline.cleaner import (
    normalize_phone,
    normalize_email,
    normalize_name,
    normalize_city,
    normalize_ctc,
    normalize_rate,
    normalize_skills,
)
from pipeline.matcher import EntityResolver
from pipeline.models import SourceRecord, UnifiedCandidate
from pipeline.db import (
    init_db,
    save_unified_candidate,
    get_all_unified_candidates,
    get_all_audio_submissions,
    find_candidate_by_phone_or_email,
)
from pipeline.ingest import run_ingestion_pipeline
from app.audio_analyzer import analyze_audio_file
from automation.simulate_n8n_flow import classify_skills_ai


class TestConsultBaePipeline(unittest.TestCase):
    """Unit tests for Data Cleaners and Entity Matcher."""

    def test_phone_normalization(self):
        self.assertEqual(normalize_phone("+919000000254"), "9000000254")
        self.assertEqual(normalize_phone("09000000287"), "9000000287")
        self.assertEqual(normalize_phone("+91-9000000131"), "9000000131")
        self.assertEqual(normalize_phone("919000000260"), "9000000260")
        self.assertEqual(normalize_phone("9000000237"), "9000000237")
        self.assertIsNone(normalize_phone(""))

    def test_email_normalization(self):
        self.assertEqual(
            normalize_email("ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG"),
            "isha.chopra95@mailtest.example.org"
        )
        self.assertEqual(
            normalize_email("  tanvi.gupta31@example.com  "),
            "tanvi.gupta31@example.com"
        )
        self.assertIsNone(normalize_email("invalid-email-address"))

    def test_name_and_city_normalization(self):
        self.assertEqual(normalize_name("RITU SHARMA"), "Ritu Sharma")
        self.assertEqual(normalize_name("R. Verma"), "R. Verma")
        self.assertEqual(normalize_city("GURGAON"), "Gurugram")
        self.assertEqual(normalize_city("bangalore"), "Bengaluru")
        self.assertEqual(normalize_city("new delhi"), "Delhi NCR")
        self.assertEqual(normalize_city("pune"), "Pune")

    def test_ctc_normalization(self):
        lpa, raw = normalize_ctc(417964)
        self.assertEqual(lpa, 4.18)
        self.assertEqual(raw, 417964)

        lpa2, raw2 = normalize_ctc("4.2")
        self.assertEqual(lpa2, 4.20)
        self.assertEqual(raw2, 420000)

    def test_rate_normalization(self):
        r1 = normalize_rate("1415/hr")
        self.assertEqual(r1["rate_type"], "hourly")
        self.assertEqual(r1["rate_amount"], 1415.0)

        r2 = normalize_rate("72k/month")
        self.assertEqual(r2["rate_type"], "monthly")
        self.assertEqual(r2["rate_amount"], 72000.0)

    def test_skills_normalization(self):
        skills = normalize_skills("n8n, LangChain, REST APIs, MongoDB, SQL, python")
        self.assertIn("n8n", skills)
        self.assertIn("LangChain", skills)
        self.assertIn("REST APIs", skills)
        self.assertIn("Python", skills)
        self.assertEqual(len(skills), 6)


class TestAudioAnalysisEngine(unittest.TestCase):
    """Tests audio feature extraction mathematics."""

    def setUp(self):
        self.test_wav = BASE_DIR / "temp_unit_test.wav"
        sample_rate = 44100
        duration = 2.5
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        # 440 Hz pure tone at amplitude 0.5
        signal = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        int16_sig = (signal * 32767).astype(np.int16)

        with wave.open(str(self.test_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int16_sig.tobytes())

    def tearDown(self):
        if self.test_wav.exists():
            self.test_wav.unlink()

    def test_audio_properties_extraction(self):
        res = analyze_audio_file(self.test_wav)
        self.assertEqual(res["duration_seconds"], 2.5)
        self.assertEqual(res["sample_rate_khz"], 44.1)
        self.assertGreater(res["bitrate_kbps"], 600.0)
        self.assertAlmostEqual(res["loudness_dbfs"], -9.03, delta=0.5)
        self.assertIn("quality_verdict", res)


class TestFullIngestionPipeline(unittest.TestCase):
    """Tests Task 1 full ingestion into SQLite."""

    def test_pipeline_execution(self):
        test_db = BASE_DIR / "test_consultbae.db"
        metrics = run_ingestion_pipeline(test_db, verbose=False)
        self.assertEqual(metrics["total_source_records"], 103)
        self.assertEqual(metrics["unified_candidates_count"], 55)
        self.assertEqual(metrics["three_sources_merged"], 15)

        candidates = get_all_unified_candidates(test_db)
        self.assertEqual(len(candidates), 55)

        # Check multi-source candidate Tanvi Gupta
        tanvi = [c for c in candidates if c["email"] == "tanvi.gupta31@example.com"][0]
        self.assertEqual(tanvi["phone"], "9000000254")
        self.assertEqual(tanvi["city"], "Bengaluru")
        self.assertEqual(len(tanvi["sources_merged"]), 3)

        if test_db.exists():
            test_db.unlink()


class TestTask2Automation(unittest.TestCase):
    """Tests Task 2 AI Classifier Simulation."""

    def test_ai_skill_classifier(self):
        cand = {
            "skills": ["n8n", "Zapier", "LangChain", "Python"],
            "experience_years": 4.5
        }
        res = classify_skills_ai(cand)
        self.assertEqual(res["primary_category"], "automation-heavy")
        self.assertEqual(res["seniority_level"], "Senior")


if __name__ == "__main__":
    unittest.main()
