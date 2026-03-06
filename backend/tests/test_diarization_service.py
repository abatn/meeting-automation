import pytest
import asyncio
from unittest.mock import patch
from app.services.diarization_service import DiarizationService

@pytest.mark.asyncio
@patch("app.services.diarization_service.DiarizationService.get_pipeline")
async def test_diarize_no_pipeline(mock_get_pipeline):
    # Setup mock to return None
    mock_get_pipeline.return_value = None

    segments = await DiarizationService.diarize("test.wav")
    assert segments == []

@pytest.mark.asyncio
@patch("app.services.diarization_service.DiarizationService.get_pipeline")
@patch("app.services.diarization_service.DiarizationService.resample_audio")
async def test_diarize_success(mock_resample, mock_get_pipeline):
    class MockPipeline:
        def __call__(self, audio_path):
            class MockDiarization:
                def itertracks(self, yield_label):
                    class Turn:
                        def __init__(self, start, end):
                            self.start = start
                            self.end = end
                    yield Turn(0.0, 2.5), None, "SPEAKER_00"
                    yield Turn(2.6, 5.0), None, "SPEAKER_01"
            return MockDiarization()

    mock_get_pipeline.return_value = MockPipeline()
    mock_resample.return_value = True

    segments = await DiarizationService.diarize("test.wav")
    
    assert len(segments) == 2
    assert segments[0]["speaker"] == "SPEAKER_00"
    assert segments[0]["start"] == 0.0
    assert segments[0]["end"] == 2.5
    assert segments[1]["speaker"] == "SPEAKER_01"
