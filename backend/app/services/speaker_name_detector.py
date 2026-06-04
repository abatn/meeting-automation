import re
import logging
import difflib
from typing import List, Optional

logger = logging.getLogger(__name__)

SELF_INTRODUCTION_PATTERNS = [
    # More specific patterns first (to avoid false matches)
    # English: "my name is Sarah", "this is Ahmed speaking", "I'm Mohamed"
    (r"my\s+name\s+is\s+([\w]+)", "english_name_is"),
    (r"this\s+is\s+([\w]+)\s+(speaking|here|talking)", "english_this_is"),
    (r"i'm\s+([\w]+)", "english_im"),
    # Arabic: "أنا أحمد", "اسمي سارة"
    (r"أنا\s+([\w\u0600-\u06FF]+)", "arabic_ana"),
    (r"اسمي\s+([\w\u0600-\u06FF]+)", "arabic_ismi"),
    # French: "je suis Ahmed", "mon nom est Sarah", "moi c'est Fatima"
    (r"je\s+suis\s+([\w]+)", "french_je_suis"),
    (r"mon\s+nom\s+est\s+([\w]+)", "french_nom_est"),
    (r"moi\s+c'est\s+([\w]+)", "french_moi_cest"),
    # German: "ich bin Ahmed", "mein Name ist Sarah"
    (r"ich\s+bin\s+([\w]+)", "german_ich_bin"),
    (r"mein\s+name\s+ist\s+([\w]+)", "german_name_ist"),
]

FUZZY_THRESHOLD = 0.75


def normalize_name(name: str) -> str:
    """Normalize name for comparison: lowercase, strip, remove diacritics."""
    name = name.strip().lower()
    # Remove common Arabic diacritics
    diacritics = re.compile(r'[\u064B-\u065F\u0670]')
    name = diacritics.sub('', name)
    return name


def fuzzy_match(extracted: str, candidates: List[str], threshold: float = FUZZY_THRESHOLD) -> Optional[str]:
    """
    Fuzzy match extracted name against candidate list.
    Returns the candidate name if match found, None otherwise.

    Matching strategy (in order):
    1. Exact match (case-insensitive, stripped)
    2. Substring match (either direction)
    3. SequenceMatcher fuzzy similarity (handles variants like AbdulQader/Abdelkader)
    """
    extracted_norm = normalize_name(extracted)

    best_score = 0.0
    best_candidate = None

    for candidate in candidates:
        candidate_norm = normalize_name(candidate)

        # Exact match
        if extracted_norm == candidate_norm:
            return candidate

        # Substring match (either direction)
        if extracted_norm in candidate_norm or candidate_norm in extracted_norm:
            return candidate

        # SequenceMatcher fuzzy similarity
        score = difflib.SequenceMatcher(None, extracted_norm, candidate_norm).ratio()
        if score > best_score:
            best_score = score
            best_candidate = candidate

    if best_score >= threshold and best_candidate:
        logger.info(f"Fuzzy match: '{extracted}' → '{best_candidate}' (score={best_score:.2f})")
        return best_candidate

    return None


def detect_self_introduction(text: str, candidates: List[str]) -> Optional[str]:
    """
    Detect self-introduction in text and match against candidate list.

    Args:
        text: Transcript text from a speaker
        candidates: List of valid candidate names (participants + enrolled profiles)

    Returns:
        Matched candidate name or None if no self-introduction detected
    """
    if not text or not text.strip():
        return None

    if not candidates:
        return None

    for pattern, pattern_name in SELF_INTRODUCTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            extracted_name = match.group(1)
            logger.debug(f"Self-introduction detected ({pattern_name}): '{extracted_name}'")

            matched_candidate = fuzzy_match(extracted_name, candidates)
            if matched_candidate:
                logger.info(f"Name '{extracted_name}' matched candidate '{matched_candidate}'")
                return matched_candidate
            else:
                logger.debug(f"Name '{extracted_name}' not in candidates: {candidates}")

    return None
