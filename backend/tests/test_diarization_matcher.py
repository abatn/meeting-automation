import pytest
from app.tasks.transcription_tasks import match_timestamps

def test_match_timestamps_basic():
    words = [
        {"word": "Hallo", "start": 0.0, "end": 0.5},
        {"word": "wie", "start": 0.6, "end": 1.0},
        {"word": "geht's?", "start": 1.1, "end": 1.5},
        {"word": "Gut,", "start": 2.0, "end": 2.5},
        {"word": "danke.", "start": 2.6, "end": 3.0}
    ]

    segments = [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 1.8},
        {"speaker": "SPEAKER_01", "start": 1.9, "end": 3.5}
    ]

    matched = match_timestamps(words, segments)

    assert len(matched) == 2
    assert matched[0]["speaker"] == "SPEAKER_00"
    assert matched[0]["text"] == "Hallo wie geht's?"
    assert matched[1]["speaker"] == "SPEAKER_01"
    assert matched[1]["text"] == "Gut, danke."

def test_match_timestamps_boundary():
    # Word exactly on the boundary
    words = [
        {"word": "Test", "start": 1.0, "end": 2.0}
    ]
    # Midpoint is 1.5
    segments = [
        {"speaker": "SPEAKER_00", "start": 0.0, "end": 1.4},
        {"speaker": "SPEAKER_01", "start": 1.6, "end": 3.0}
    ]

    matched = match_timestamps(words, segments)
    assert len(matched) == 1
    # Closest by absolute distance to midpoint
    # Dist to SPEAKER_00 end (1.4) is 0.1
    # Dist to SPEAKER_01 start (1.6) is 0.1
    # Min function will pick the first one
    assert matched[0]["speaker"] == "SPEAKER_00"

def test_match_timestamps_empty():
    assert match_timestamps([], [{"speaker": "S1", "start": 0, "end": 1}]) == []
    assert match_timestamps([{"word": "A", "start": 0, "end": 1}], []) == []
