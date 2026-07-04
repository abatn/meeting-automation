import re
import logging
import difflib
from typing import List, Optional

logger = logging.getLogger(__name__)

ARABIC_TO_LATIN = {
    '\u0627': 'a', '\u0623': 'a', '\u0625': 'i', '\u0622': 'a',
    '\u0628': 'b', '\u062A': 't', '\u062B': 'th', '\u062C': 'j',
    '\u062D': 'h', '\u062E': 'kh', '\u062F': 'd', '\u0630': 'dh',
    '\u0631': 'r', '\u0632': 'z', '\u0633': 's', '\u0634': 'sh',
    '\u0635': 's', '\u0636': 'dh', '\u0637': 't', '\u0638': 'dh',
    '\u0639': 'a', '\u063A': 'gh', '\u0641': 'f', '\u0642': 'q',
    '\u0643': 'k', '\u0644': 'l', '\u0645': 'm', '\u0646': 'n',
    '\u0647': 'h', '\u0648': 'w', '\u064A': 'y', '\u0649': 'a',
    '\u0629': 'a',
}


def transliterate_arabic(text: str) -> str:
    """Transliterate Arabic text to Latin characters for cross-script matching."""
    result = []
    for char in text:
        if char in ARABIC_TO_LATIN:
            result.append(ARABIC_TO_LATIN[char])
        elif char.isalpha() or char == ' ':
            result.append(char.lower())
    return ''.join(result)


SELF_INTRODUCTION_PATTERNS = [
    (r"my\s+name\s+is\s+([\w]+)", "english_name_is"),
    (r"this\s+is\s+([\w]+)\s+(speaking|here|talking)", "english_this_is"),
    (r"i'm\s+([\w]+)", "english_im"),
    (r"\u0623\u0646\u0627\s+(.+?)(?:\s*[,.\u060c]|\s+(?:\u0648|\u0645\u0639|\u0634\u0643\u0631\u0627|\u0627\u0644\u0633\u064a\u062f)|\s*$)", "arabic_ana"),
    (r"\u0627\u0633\u0645\u064a\s+(.+?)(?:\s*[,.\u060c]|\s+(?:\u0648|\u0645\u0639|\u0634\u0643\u0631\u0627)|\s*$)", "arabic_ismi"),
    (r"\u0627\u0646\u0627\s+(.+?)(?:\s*[,.\u060c]|\s+(?:\u0648|\u0645\u0639|\u0634\u0643\u0631\u0627)|\s*$)", "arabic_ana_short"),
    (r"\u0645\u0639\u0627\u0643\u0645\s+(?:\u0627\u0644\u0633\u064a\u062f\s+)?(.+?)(?:\s*[,.\u060c]|\s*$)", "arabic_maakum"),
    (r"\u0627\u0644\u0633\u064a\u062f\s+(.+?)(?:\s+[\u0627\u0644\u0628\u0637\u0646\u064a\u0646\u064a]|\s*[,.\u060c]|\s*$)", "arabic_alsayyid"),
    (r"je\s+suis\s+([\w]+)", "french_je_suis"),
    (r"mon\s+nom\s+est\s+([\w]+)", "french_nom_est"),
    (r"moi\s+c'est\s+([\w]+)", "french_moi_cest"),
    (r"ich\s+bin\s+([\w]+)", "german_ich_bin"),
    (r"mein\s+name\s+ist\s+([\w]+)", "german_name_ist"),
]

FUZZY_THRESHOLD = 0.75


def normalize_name(name: str) -> str:
    """Normalize name for comparison: lowercase, strip, remove diacritics."""
    name = name.strip().lower()
    diacritics = re.compile(r'[\u064B-\u065F\u0670]')
    name = diacritics.sub('', name)
    return name


def _strip_vowels(name: str) -> str:
    """Remove vowels for consonant-only matching (helps Arabic↔Latin)."""
    return re.sub(r'[aeiou\s]', '', name.lower())


def _names_match_cross_script(extracted_norm: str, candidate_norm: str) -> bool:
    """Check if an Arabic name matches a Latin candidate via transliteration."""
    if any('\u0600' <= c <= '\u06FF' for c in extracted_norm):
        transliterated = transliterate_arabic(extracted_norm)

        if transliterated == candidate_norm:
            return True
        if transliterated in candidate_norm or candidate_norm in transliterated:
            return True

        score = difflib.SequenceMatcher(None, transliterated, candidate_norm).ratio()
        if score >= FUZZY_THRESHOLD:
            return True

        extracted_consonants = _strip_vowels(transliterated)
        candidate_consonants = _strip_vowels(candidate_norm)
        consonant_score = difflib.SequenceMatcher(None, extracted_consonants, candidate_consonants).ratio()
        if consonant_score >= 0.80:
            logger.info(f"Consonant match: '{extracted_norm}' → '{candidate_norm}' "
                        f"(consonant_score={consonant_score:.2f})")
            return True

    return False


def fuzzy_match(extracted: str, candidates: List[str], threshold: float = FUZZY_THRESHOLD) -> Optional[str]:
    """
    Fuzzy match extracted name against candidate list.
    Returns the candidate name if match found, None otherwise.

    Matching strategy (in order):
    1. Exact match (case-insensitive, stripped)
    2. Substring match (either direction)
    3. Cross-script transliteration match (Arabic ↔ Latin)
    4. SequenceMatcher fuzzy similarity
    """
    extracted_norm = normalize_name(extracted)

    best_score = 0.0
    best_candidate = None

    for candidate in candidates:
        candidate_norm = normalize_name(candidate)

        if extracted_norm == candidate_norm:
            return candidate

        if extracted_norm in candidate_norm or candidate_norm in extracted_norm:
            return candidate

        if _names_match_cross_script(extracted_norm, candidate_norm):
            logger.info(f"Cross-script match: '{extracted}' → '{candidate}'")
            return candidate

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
    Supports English, Arabic, French, German patterns.
    """
    if not text or not text.strip():
        return None

    if not candidates:
        return None

    for pattern, pattern_name in SELF_INTRODUCTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            extracted_name = match.group(1).strip()
            logger.info(f"Self-introduction detected ({pattern_name}): '{extracted_name}'")

            matched_candidate = fuzzy_match(extracted_name, candidates)
            if matched_candidate:
                logger.info(f"Name '{extracted_name}' matched candidate '{matched_candidate}'")
                return matched_candidate
            else:
                logger.info(f"Name '{extracted_name}' not in candidates: {candidates}")

    return None
