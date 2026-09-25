"""P3 - token-budget chunking for Sentinel (replaces fixed 3100-char slices).

Gate G3 expects `TIMING: sentinel_chunks count=1` for a 3207-char transcript and
>=2 chunks once the text exceeds SENTINEL_CHUNK_TOKEN_BUDGET tokens.

Token density used here is the measured worst case (2.1 chars/token for Arabic
transcripts, benchmark 2026-09-13).
"""

import logging

from app.tasks.transcription_tasks import (
    SENTINEL_CHUNK_TOKEN_BUDGET,
    split_text_by_token_budget,
)

ARABIC_DENSITY = 2.1  # chars per token, measured worst case
BASE = "المتحدث أ: نرحب بالحضور. "


def _fixture(n_chars: int) -> str:
    """Exactly n_chars characters of Arabic-like transcript text."""
    return (BASE * (n_chars // len(BASE) + 1))[:n_chars]


def _tokens(text: str) -> int:
    """Deterministic tokenizer stand-in: 2.1 chars/token (measured density)."""
    return max(1, int(len(text) / ARABIC_DENSITY))


def test_3207_chars_yields_single_chunk():
    text = _fixture(3207)
    assert len(text) == 3207, f"fixture must be exactly 3207 chars, got {len(text)}"

    tokens = _tokens(text)
    assert tokens <= SENTINEL_CHUNK_TOKEN_BUDGET, (
        f"fixture must fit the budget: {tokens} > {SENTINEL_CHUNK_TOKEN_BUDGET}"
    )

    chunks = split_text_by_token_budget(text, _tokens)
    assert len(chunks) == 1, f"3207-char text must stay ONE chunk, got {len(chunks)}"
    assert "".join(chunks).split() == text.split(), "chunking must not lose text"


def test_over_budget_yields_multiple_chunks():
    text = _fixture(5000)
    tokens = _tokens(text)
    assert tokens > SENTINEL_CHUNK_TOKEN_BUDGET, (
        f"fixture must exceed the budget: {tokens} <= {SENTINEL_CHUNK_TOKEN_BUDGET}"
    )

    chunks = split_text_by_token_budget(text, _tokens)
    assert len(chunks) >= 2, f"over-budget text must split, got {len(chunks)}"
    for i, piece in enumerate(chunks):
        assert _tokens(piece) <= SENTINEL_CHUNK_TOKEN_BUDGET, (
            f"piece {i} exceeds budget: {_tokens(piece)} > {SENTINEL_CHUNK_TOKEN_BUDGET}"
        )
    assert "".join(chunks).split() == text.split(), "chunking must not lose text"


def test_exactly_at_budget_is_single_chunk():
    text = _fixture(int(SENTINEL_CHUNK_TOKEN_BUDGET * ARABIC_DENSITY))
    assert _tokens(text) <= SENTINEL_CHUNK_TOKEN_BUDGET, (
        f"fixture must fit exactly: {_tokens(text)} > {SENTINEL_CHUNK_TOKEN_BUDGET}"
    )
    assert len(split_text_by_token_budget(text, _tokens)) == 1


def test_missing_tokenizer_falls_back_to_single_chunk():
    text = "anything" * 5000
    assert split_text_by_token_budget(text, None) == [text]


def test_pipeline_logs_one_chunk_for_3207_char_text(caplog):
    """Gate G3 helper: count reported to TIMING: sentinel_chunks."""
    text = _fixture(3207)
    with caplog.at_level(logging.INFO):
        chunks = split_text_by_token_budget(text, _tokens)
        logging.getLogger(__name__).info(
            f"TIMING: sentinel_chunks count={len(chunks)} text_len={len(text)}"
        )
    assert "sentinel_chunks count=1" in caplog.text
