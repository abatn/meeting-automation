"""
Double Metaphone phonetic algorithm for name comparison.

Handles spelling variants of names:
- Mohammed / Muhammad / Mohammad
- Abdelkader / Abdulqader / Abd al-Qadir
- Fatima / Fatema / Fatimah

Based on the Double Metaphone algorithm by Lawrence Philips.
"""

import re
from typing import Tuple, List


class DoubleMetaphone:
    """Double Metaphone phonetic encoding algorithm."""

    def __init__(self):
        self._vowels = set('AEIOUY')

    def encode(self, word: str) -> Tuple[str, str]:
        """
        Encode a word into two phonetic codes.
        Returns (primary, secondary) codes.
        """
        if not word:
            return ("", "")

        word = word.upper().strip()
        # Remove non-alphabetic characters
        word = re.sub(r'[^A-Z]', '', word)

        if not word:
            return ("", "")

        length = len(word)
        primary = []
        secondary = []
        last = length - 1
        current = 0

        # Skip initial silent letters
        if word.startswith(('GN', 'KN', 'PN', 'AE', 'WR')):
            current = 1

        # Initial 'X' is pronounced 'Z'
        if word[0] == 'X':
            primary.append('S')
            secondary.append('S')
            current = 1

        while current <= last:
            ch = word[current]

            if ch in self._vowels:
                if current == 0:
                    primary.append('A')
                    secondary.append('A')
                current += 1
                continue

            if ch == 'B':
                primary.append('P')
                secondary.append('P')
                current += 1
                if current <= last and word[current] == 'B':
                    current += 1

            elif ch == 'C':
                # Various Germanic
                if current > 1 and word[current - 1] not in self._vowels \
                   and word[current - 1] != 'A' \
                   and word[current + 1:current + 3] == 'ER':
                    primary.append('K')
                    secondary.append('K')
                    current += 2
                elif word[current + 1:current + 3] == 'CH':
                    primary.append('X')
                    secondary.append('X')
                    current += 2
                elif word[current + 1:current + 2] == 'H':
                    if current == 0 or (current > 1 and word[current - 2] in self._vowels):
                        primary.append('K')
                        secondary.append('K')
                    else:
                        primary.append('X')
                        secondary.append('X')
                    current += 2
                elif word[current + 1:current + 3] in ('CI', 'CE', 'CY'):
                    primary.append('S')
                    secondary.append('S')
                    current += 2
                elif word[current + 1:current + 3] in ('CK', 'CG'):
                    primary.append('K')
                    secondary.append('K')
                    current += 2
                else:
                    primary.append('K')
                    secondary.append('K')
                    current += 1

            elif ch == 'D':
                primary.append('T')
                secondary.append('T')
                current += 1
                if current <= last and word[current] == 'D':
                    current += 1

            elif ch == 'F':
                primary.append('F')
                secondary.append('F')
                current += 1
                if current <= last and word[current] == 'F':
                    current += 1

            elif ch == 'G':
                if current <= last - 1 and word[current + 1] == 'H':
                    if current == 0 or (current > 1 and word[current - 1] not in self._vowels):
                        primary.append('K')
                        secondary.append('K')
                    current += 2
                elif current <= last - 1 and word[current + 1] == 'N':
                    if current == 0:
                        primary.append('N')
                        secondary.append('K')
                    else:
                        primary.append('K')
                        secondary.append('K')
                    current += 2
                elif word[current + 1:current + 3] in ('GN', 'GNE'):
                    primary.append('N')
                    secondary.append('N')
                    current += 2
                elif current <= last - 1 and word[current + 1] in ('E', 'I', 'Y'):
                    primary.append('J')
                    secondary.append('K')
                    current += 2
                else:
                    primary.append('K')
                    secondary.append('K')
                    current += 1
                    if current <= last and word[current] == 'G':
                        current += 1

            elif ch == 'H':
                if current == 0 or (current <= last and word[current - 1] in self._vowels):
                    if current <= last and word[current + 1] in self._vowels:
                        primary.append('H')
                        secondary.append('H')
                        current += 2
                    else:
                        current += 1
                else:
                    current += 1

            elif ch == 'J':
                primary.append('J')
                secondary.append('J')
                current += 1
                if current <= last and word[current] == 'J':
                    current += 1

            elif ch == 'K':
                primary.append('K')
                secondary.append('K')
                current += 1
                if current <= last and word[current] == 'K':
                    current += 1

            elif ch == 'L':
                primary.append('L')
                secondary.append('L')
                current += 1
                if current <= last and word[current] == 'L':
                    current += 1

            elif ch == 'M':
                primary.append('M')
                secondary.append('M')
                current += 1
                if current <= last and word[current] == 'M':
                    current += 1

            elif ch == 'N':
                primary.append('N')
                secondary.append('N')
                current += 1
                if current <= last and word[current] == 'N':
                    current += 1

            elif ch == 'P':
                if current <= last and word[current + 1] == 'H':
                    primary.append('F')
                    secondary.append('F')
                    current += 2
                else:
                    primary.append('P')
                    secondary.append('P')
                    current += 1
                    if current <= last and word[current] == 'P':
                        current += 1

            elif ch == 'Q':
                primary.append('K')
                secondary.append('K')
                current += 1
                if current <= last and word[current] == 'Q':
                    current += 1

            elif ch == 'R':
                primary.append('R')
                secondary.append('R')
                current += 1
                if current <= last and word[current] == 'R':
                    current += 1

            elif ch == 'S':
                if current <= last - 2 and word[current + 1:current + 3] == 'CH':
                    primary.append('X')
                    secondary.append('X')
                    current += 3
                elif current <= last - 1 and word[current + 1] == 'H':
                    primary.append('X')
                    secondary.append('X')
                    current += 2
                elif current <= last - 2 and word[current + 1:current + 3] in ('SI', 'IO'):
                    primary.append('S')
                    secondary.append('X')
                    current += 2
                else:
                    primary.append('S')
                    secondary.append('S')
                    current += 1
                    if current <= last and word[current] == 'S':
                        current += 1

            elif ch == 'T':
                if current <= last - 2 and word[current + 1:current + 3] == 'CH':
                    primary.append('X')
                    secondary.append('X')
                    current += 3
                elif current <= last - 1 and word[current + 1] == 'H':
                    primary.append('0')  # TH sound
                    secondary.append('T')
                    current += 2
                elif current <= last - 2 and word[current + 1:current + 3] in ('TI', 'IO'):
                    primary.append('S')
                    secondary.append('X')
                    current += 2
                else:
                    primary.append('T')
                    secondary.append('T')
                    current += 1
                    if current <= last and word[current] == 'T':
                        current += 1

            elif ch == 'V':
                primary.append('F')
                secondary.append('F')
                current += 1
                if current <= last and word[current] == 'V':
                    current += 1

            elif ch == 'W':
                if current <= last and word[current + 1] in self._vowels:
                    primary.append('A')
                    secondary.append('F')
                    current += 2
                else:
                    current += 1

            elif ch == 'X':
                if current == 0:
                    primary.append('S')
                    secondary.append('S')
                else:
                    primary.append('KS')
                    secondary.append('KS')
                current += 1
                if current <= last and word[current] == 'X':
                    current += 1

            elif ch == 'Y':
                if current <= last and word[current + 1] in self._vowels:
                    primary.append('A')
                    secondary.append('A')
                    current += 2
                else:
                    current += 1

            elif ch == 'Z':
                primary.append('S')
                secondary.append('S')
                current += 1
                if current <= last and word[current] == 'Z':
                    current += 1

            else:
                current += 1

        primary_str = ''.join(primary)[:4]
        secondary_str = ''.join(secondary)[:4]

        return (primary_str, secondary_str)


def phonetic_match(name1: str, name2: str) -> float:
    """
    Calculate phonetic similarity between two names.
    Returns a score between 0.0 and 1.0.

    Uses Double Metaphone encoding + string similarity.
    """
    if not name1 or not name2:
        return 0.0

    n1 = name1.strip().lower()
    n2 = name2.strip().lower()

    # Exact match
    if n1 == n2:
        return 1.0

    # Double Metaphone encoding
    dm = DoubleMetaphone()
    p1, s1 = dm.encode(n1)
    p2, s2 = dm.encode(n2)

    # Primary code match
    if p1 == p2 and p1:
        return 0.85

    # Primary vs secondary match
    if p1 == s2 or s1 == p2:
        return 0.75

    # Both secondary codes match
    if s1 == s2 and s1:
        return 0.70

    # Partial phonetic overlap (first 2 chars)
    if p1[:2] == p2[:2] and p1[:2]:
        return 0.60

    # No phonetic match
    return 0.0


def phonetic_candidates(query: str, candidates: List[str], threshold: float = 0.60) -> List[Tuple[str, float]]:
    """
    Find phonetic matches for a query name among candidates.
    Returns list of (candidate_name, score) tuples sorted by score.
    """
    matches = []
    for candidate in candidates:
        score = phonetic_match(query, candidate)
        if score >= threshold:
            matches.append((candidate, score))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches
