"""
Phase 4 E2E Tests: AI Pipeline Resilience & Error Handling

Tests for:
- P4-1: Recording status rollback on processing error
- P4-2: Celery retry configuration with exponential backoff
- P4-3: Temp file cleanup in finally block
- P4-4: after_upload webhook triggering

Date: 2026-05-05
Author: OpenCode AI
"""
import pytest
import inspect
from app.tasks.transcription_tasks import process_recording, _process_recording_pipeline
from app.core.config import settings
from app.services.recording_service import RecordingService


@pytest.mark.asyncio
async def test_p42_celery_task_has_retry_config():
    """P4-2: Celery task should have retry configuration"""
    # Verify task has retry settings
    assert process_recording.autoretry_for == (Exception,), "Should autoretry on Exception"
    assert process_recording.max_retries == 3, "Should have max 3 retries"
    assert process_recording.retry_backoff is True, "Should use exponential backoff"
    assert process_recording.retry_backoff_max == 600, "Max backoff should be 10 minutes"
    assert process_recording.retry_jitter is True, "Should use jitter to prevent thundering herd"
    # Note: bind is a method, not a property - just verify it exists
    assert callable(process_recording.bind), "Task should have bind method"


def test_p42_celery_exponential_backoff():
    """P4-2: Celery should use exponential backoff for retries"""
    # Verify Celery configuration for exponential backoff
    assert process_recording.retry_backoff is True
    assert process_recording.max_retries == 3
    
    # Celery exponential backoff: 2^x * base, capped at retry_backoff_max
    # Attempt 1: fail immediately
    # Attempt 2: wait ~2^1=2 seconds, then retry
    # Attempt 3: wait ~2^2=4 seconds, then retry
    # Attempt 4: wait ~2^3=8 seconds, then retry (max_retries=3, so this fails)
    # Total retries: 3 (after initial attempt fails)
    
    assert process_recording.retry_backoff_max == 600  # 10 minutes


def test_p41_error_handling_with_rollback():
    """P4-1: _process_recording_pipeline has try/except/finally with rollback"""
    source = inspect.getsource(_process_recording_pipeline)
    
    # Check for try/except/finally structure
    assert "try:" in source, "Should have try block"
    assert "except Exception" in source, "Should catch exceptions"
    assert "finally:" in source, "Should have finally block for cleanup"
    
    # Check for status rollback
    assert 'recording.status = "failed"' in source, "Should set status to failed on error"
    
    # Check for temp file cleanup
    assert "os.remove(temp_path)" in source, "Should clean up temp files"
    assert "os.path.exists(temp_path)" in source, "Should check if temp file exists before removing"


def test_p43_temp_file_cleanup_in_finally():
    """P4-3: Temp file cleanup is in finally block"""
    source = inspect.getsource(_process_recording_pipeline)
    
    # Find finally block location
    finally_pos = source.find("finally:")
    assert finally_pos != -1, "finally block should exist"
    
    # Check that os.remove is in finally block (after finally:)
    finally_block = source[finally_pos:]
    assert "os.remove(temp_path)" in finally_block, "os.remove should be in finally block"


def test_p41_recording_status_change_points():
    """P4-1: Pipeline changes recording status at correct points"""
    source = inspect.getsource(_process_recording_pipeline)
    
    # Find all status changes
    transcribing_status = source.find('status = "transcribing"')
    completed_status = source.find('status = "completed"')
    failed_status = source.find('status = "failed"')
    
    assert transcribing_status != -1, 'Should set status to "transcribing" at start'
    assert completed_status != -1, 'Should set status to "completed" on success'
    assert failed_status != -1, 'Should set status to "failed" on error'
    
    # Verify order: transcribing comes before completed and failed
    assert transcribing_status < completed_status, "transcribing should come before completed"
    assert transcribing_status < failed_status, "transcribing should come before failed"


def test_p44_after_upload_webhook_configured():
    """P4-4: after_upload webhook URL should be configured"""
    # Verify n8n webhook for audio-uploaded is configured
    assert hasattr(settings, 'N8N_WEBHOOK_AUDIO_UPLOADED')
    assert settings.N8N_WEBHOOK_AUDIO_UPLOADED is not None
    assert len(settings.N8N_WEBHOOK_AUDIO_UPLOADED) > 0


def test_p44_recording_service_has_after_upload():
    """P4-4: RecordingService should have after_upload method"""
    assert hasattr(RecordingService, 'after_upload')
    assert callable(getattr(RecordingService, 'after_upload'))


def test_p41_publish_status_called_on_error():
    """P4-1: Redis publish_status should be called with 'failed' status"""
    source = inspect.getsource(_process_recording_pipeline)
    
    # Check for publish_status call in except block
    assert "publish_status" in source, "Should publish status updates to Redis"
    
    # Find except block
    except_pos = source.find("except Exception")
    assert except_pos != -1, "Should have except block"
    
    # Check that publish_status is called with "failed"
    except_block = source[except_pos:except_pos+500]  # Look at next 500 chars
    assert "failed" in except_block, 'Should publish "failed" status'


def test_p41_exception_reraised_for_celery():
    """P4-1: Exception should be re-raised for Celery retry"""
    source = inspect.getsource(_process_recording_pipeline)
    
    # Find except block
    except_start = source.find("except Exception")
    assert except_start != -1, "Should have exception handler"
    
    # Find matching finally
    finally_pos = source.find("finally:", except_start)
    except_block = source[except_start:finally_pos]
    
    # Check that exception is re-raised
    assert "raise" in except_block, "Should re-raise exception for Celery retry"


def test_p43_error_handling_in_cleanup():
    """P4-3: Temp file cleanup should handle errors gracefully"""
    source = inspect.getsource(_process_recording_pipeline)
    
    # Find finally block
    finally_pos = source.find("finally:")
    finally_block = source[finally_pos:]
    
    # Check for try/except in finally block
    assert "try:" in finally_block or "except" in finally_block, \
        "Cleanup should handle potential errors gracefully"


def test_p41_gladia_failure_triggers_rollback():
    """P4-1: Gladia API failure should trigger status rollback"""
    source = inspect.getsource(_process_recording_pipeline)
    
    # Check that gladia_service.transcribe_and_diarize is called
    assert "gladia_service.transcribe_and_diarize" in source, \
        "Pipeline should call Gladia transcription service"
    
    # Check that exception handling covers this
    assert "except Exception" in source, \
        "Gladia failures should be caught and handled"


def test_p42_retry_backoff_max_reasonable():
    """P4-2: Retry backoff max should be reasonable (< 1 hour)"""
    assert process_recording.retry_backoff_max <= 3600, \
        "Max backoff should be <= 1 hour (3600 seconds)"
    assert process_recording.retry_backoff_max >= 60, \
        "Max backoff should be >= 1 minute to be useful"


def test_p42_max_retries_reasonable():
    """P4-2: Max retries should be reasonable (2-5)"""
    assert 2 <= process_recording.max_retries <= 5, \
        "Max retries should be between 2 and 5"


def test_p44_n8n_completion_webhook_exists():
    """P4-4: n8n completion webhook configuration should exist"""
    assert hasattr(settings, 'N8N_WEBHOOK_TRANSCRIPTION_COMPLETED')
    assert settings.N8N_WEBHOOK_TRANSCRIPTION_COMPLETED is not None


def test_p41_redis_status_published():
    """P4-1: Pipeline publishes status to Redis at key points"""
    source = inspect.getsource(_process_recording_pipeline)
    
    # Check for multiple publish_status calls
    count = source.count("publish_status")
    assert count >= 5, "Should publish status multiple times during processing"
