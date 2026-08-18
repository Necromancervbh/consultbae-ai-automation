"""
Data Cleaning & Normalization Engine for ConsultBae Datasets.
Standardizes phone numbers, emails, names, cities, dates, compensation, and skill tags.
"""

import re
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

# Canonical casing dictionary for common technical skills
CANONICAL_SKILL_MAP = {
    "n8n": "n8n",
    "fastapi": "FastAPI",
    "mysql": "MySQL",
    "mongodb": "MongoDB",
    "docker": "Docker",
    "zapier": "Zapier",
    "selenium": "Selenium",
    "pandas": "Pandas",
    "langchain": "LangChain",
    "react": "React",
    "python": "Python",
    "javascript": "JavaScript",
    "rest apis": "REST APIs",
    "rest api": "REST APIs",
    "rest": "REST APIs",
    "web scraping": "Web Scraping",
    "scraping": "Web Scraping",
    "sql": "SQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "node": "Node.js",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
}

# Canonical city mapping
CANONICAL_CITY_MAP = {
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "gurugram ": "Gurugram",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "delhi": "Delhi NCR",
    "new delhi": "Delhi NCR",
    "delhi ncr": "Delhi NCR",
    "pune": "Pune",
    "noida": "Noida",
    "noida ": "Noida",
    "mumbai": "Mumbai",
    "hyderabad": "Hyderabad",
    "chennai": "Chennai",
    "kolkata": "Kolkata",
}


def normalize_phone(raw_phone: Optional[str]) -> Optional[str]:
    """
    Normalizes messy phone numbers into standard 10-digit Indian phone strings.
    Handles +91, leading 0, dashes, spaces, brackets.
    Examples:
        '+919000000254' -> '9000000254'
        '09000000287'   -> '9000000287'
        '+91-9000000131'-> '9000000131'
        '919000000260'  -> '9000000260'
        '9000000237'    -> '9000000237'
    """
    if not raw_phone:
        return None

    # Keep only digits
    digits = re.sub(r"\D", "", str(raw_phone).strip())

    if not digits:
        return None

    # If starts with 91 and has 12 digits (e.g. 919000000260)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    # If starts with 0 and has 11 digits (e.g. 09000000287)
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    # Final validation: standard 10-digit mobile number
    if len(digits) == 10 and digits[0] in "6789":
        return digits

    # Return whatever digits if 10 long
    if len(digits) == 10:
        return digits

    return digits if digits else None


def normalize_email(raw_email: Optional[str]) -> Optional[str]:
    """
    Normalizes email addresses to lowercase and validates syntax.
    Handles 'ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG' -> 'isha.chopra95@mailtest.example.org'
    """
    if not raw_email:
        return None

    cleaned = str(raw_email).strip().lower()
    if "@" in cleaned and "." in cleaned:
        # Basic regex check
        if re.match(r"^[\w\.\+\-]+@[\w\.\-]+\.[a-zA-Z0-9\.\-]+$", cleaned):
            return cleaned

    return None


def normalize_name(raw_name: Optional[str]) -> str:
    """
    Cleans name strings, removing excessive whitespace and fixing uppercase formatting.
    Examples:
        'RITU SHARMA' -> 'Ritu Sharma'
        '  Manish Reddy  ' -> 'Manish Reddy'
        'R. Verma' -> 'R. Verma'
    """
    if not raw_name:
        return "Unknown"

    cleaned = " ".join(str(raw_name).strip().split())
    if not cleaned:
        return "Unknown"

    # Title-case if all uppercase or all lowercase
    if cleaned.isupper() or cleaned.islower():
        # Handle initials like 'R. Verma' properly
        parts = cleaned.split()
        capitalized = []
        for part in parts:
            if part.endswith(".") and len(part) <= 3:
                capitalized.append(part.upper())
            else:
                capitalized.append(part.capitalize())
        return " ".join(capitalized)

    return cleaned


def normalize_city(raw_city: Optional[str]) -> str:
    """
    Standardizes city names across variants and inconsistent casing.
    """
    if not raw_city:
        return "Unknown"

    cleaned = str(raw_city).strip().lower()
    if cleaned in CANONICAL_CITY_MAP:
        return CANONICAL_CITY_MAP[cleaned]

    # Clean punctuation and return title case
    cleaned = re.sub(r"[^\w\s]", "", cleaned).strip()
    return CANONICAL_CITY_MAP.get(cleaned, cleaned.title())


def normalize_ctc(raw_ctc: Any) -> Tuple[Optional[float], Optional[int]]:
    """
    Standardizes CTC into (ctc_lpa: float, ctc_annual_inr: int).
    Handles:
        417964 (Rupees) -> (4.18 LPA, 417964 INR)
        4.2 (LPA)       -> (4.20 LPA, 420000 INR)
        '8.3'           -> (8.30 LPA, 830000 INR)
    """
    if raw_ctc is None or raw_ctc == "":
        return None, None

    try:
        val = float(str(raw_ctc).strip())
        if val <= 0:
            return None, None

        if val < 100.0:
            # Value is already in Lakhs per annum (LPA)
            ctc_lpa = round(val, 2)
            ctc_inr = int(round(val * 100000))
            return ctc_lpa, ctc_inr
        else:
            # Value is raw annual INR
            ctc_inr = int(round(val))
            ctc_lpa = round(val / 100000.0, 2)
            return ctc_lpa, ctc_inr
    except (ValueError, TypeError):
        return None, None


def normalize_rate(raw_rate: Optional[str]) -> Dict[str, Any]:
    """
    Parses rate expressions from gig workers:
    '1415/hr'    -> {'rate_type': 'hourly', 'rate_amount': 1415.0, 'monthly_inr': 226400.0}
    '15k/month'  -> {'rate_type': 'monthly', 'rate_amount': 15000.0, 'monthly_inr': 15000.0}
    '72k/month'  -> {'rate_type': 'monthly', 'rate_amount': 72000.0, 'monthly_inr': 72000.0}
    """
    if not raw_rate:
        return {"rate_type": None, "rate_amount": None, "monthly_inr": None, "raw": None}

    cleaned = str(raw_rate).strip().lower()

    # Pattern 1: Hourly rate (e.g. 1415/hr, 403/hr)
    hourly_match = re.match(r"(\d+(?:\.\d+)?)\s*(?:/|\s*per\s*)?\s*(?:hr|hour)", cleaned)
    if hourly_match:
        rate = float(hourly_match.group(1))
        # Standard assumption: 160 working hours/month for full-time equivalence
        return {
            "rate_type": "hourly",
            "rate_amount": rate,
            "monthly_inr": round(rate * 160, 2),
            "raw": raw_rate,
        }

    # Pattern 2: Monthly rate with 'k' (e.g. 15k/month, 72k/month)
    monthly_k_match = re.match(r"(\d+(?:\.\d+)?)\s*k\s*(?:/|\s*per\s*)?\s*(?:mo|month)", cleaned)
    if monthly_k_match:
        rate_k = float(monthly_k_match.group(1))
        rate_inr = rate_k * 1000.0
        return {
            "rate_type": "monthly",
            "rate_amount": rate_inr,
            "monthly_inr": round(rate_inr, 2),
            "raw": raw_rate,
        }

    # Pattern 3: Monthly plain numbers (e.g. 50000/month)
    monthly_match = re.match(r"(\d+(?:\.\d+)?)\s*(?:/|\s*per\s*)?\s*(?:mo|month)", cleaned)
    if monthly_match:
        rate_inr = float(monthly_match.group(1))
        return {
            "rate_type": "monthly",
            "rate_amount": rate_inr,
            "monthly_inr": round(rate_inr, 2),
            "raw": raw_rate,
        }

    return {"rate_type": "custom", "rate_amount": None, "monthly_inr": None, "raw": raw_rate}


def normalize_date(raw_date: Optional[str]) -> Optional[str]:
    """
    Standardizes flexible date strings into ISO 8601 'YYYY-MM-DD'.
    Handles:
        '24-07-2026', '2026-08-08', '7 Jul 2026', '07/13/2026', '08/19/2026', etc.
    """
    if not raw_date:
        return None

    cleaned = str(raw_date).strip()
    if not cleaned:
        return None

    date_formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y/%m/%d",
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return cleaned


def normalize_verified(raw_verified: Any) -> Optional[bool]:
    """
    Normalizes boolean verification flags: 'Y', 'yes', 'Yes', '1', 'True' -> True
    'N', 'no', 'No', '0', 'False' -> False
    """
    if raw_verified is None or raw_verified == "":
        return None

    cleaned = str(raw_verified).strip().lower()
    if cleaned in ("y", "yes", "true", "1", "verified"):
        return True
    if cleaned in ("n", "no", "false", "0", "unverified"):
        return False

    return None


def normalize_status(raw_status: Optional[str]) -> str:
    """
    Standardizes worker status casing: 'active', 'ACTIVE', 'Active' -> 'Active'
    'paused' -> 'Paused', 'inactive' -> 'Inactive'
    """
    if not raw_status:
        return "Unknown"

    cleaned = str(raw_status).strip().lower()
    if cleaned == "active":
        return "Active"
    elif cleaned == "paused":
        return "Paused"
    elif cleaned == "inactive":
        return "Inactive"
    return cleaned.capitalize()


def normalize_skills(raw_skills: Any) -> List[str]:
    """
    Splits, trims, deduplicates, and standardizes technical skills.
    Examples:
        'n8n, LangChain, REST APIs, MongoDB, SQL' -> ['n8n', 'LangChain', 'REST APIs', 'MongoDB', 'SQL']
        'mongodb, rest apis, fastapi, web scraping' -> ['MongoDB', 'REST APIs', 'FastAPI', 'Web Scraping']
    """
    if not raw_skills:
        return []

    if isinstance(raw_skills, list):
        items = raw_skills
    else:
        items = str(raw_skills).split(",")

    skills_set = set()
    cleaned_skills = []

    for item in items:
        token = item.strip()
        if not token:
            continue

        lower_token = token.lower()
        canonical_name = CANONICAL_SKILL_MAP.get(lower_token, token.title())

        if canonical_name.lower() not in skills_set:
            skills_set.add(canonical_name.lower())
            cleaned_skills.append(canonical_name)

    return sorted(cleaned_skills)
