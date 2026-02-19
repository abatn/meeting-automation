import pytest
from unittest.mock import AsyncMock, patch, Mock # Import Mock
import httpx
import logging
import json

from backend.app.services.mistral_client import MistralClient
from backend.app.core.config import settings

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.fixture
def mistral_client_instance():
    """Fixture to provide a MistralClient instance with mocked httpx.AsyncClient."""
    with patch('backend.app.services.mistral_client.httpx.AsyncClient') as MockAsyncClient:
        mock_client = MockAsyncClient.return_value
        # Create a mock response object that has a non-async raise_for_status
        mock_response_obj = AsyncMock(
            status_code=200,
            json=AsyncMock(return_value={"choices": [{"message": {"content": "Default Mocked Response"}}]})
        )
        mock_response_obj.raise_for_status = Mock(return_value=None) # Ensure it's a regular Mock
        mock_client.post = AsyncMock(return_value=mock_response_obj)
        yield MistralClient()

@pytest.mark.asyncio
async def test_call_mistral_api_success(mistral_client_instance):
    """Test successful API call."""
    mock_response_data = {"choices": [{"message": {"content": "Test PV"}}]}
    mock_http_response = AsyncMock(
        status_code=200,
        json=AsyncMock(return_value=mock_response_data)
    )
    mock_http_response.raise_for_status = Mock(return_value=None) # Ensure it's a regular Mock
    mistral_client_instance.client.post.return_value = mock_http_response

    response = await mistral_client_instance.call_mistral_api("/v1/chat/completions", {"prompt": "test"})
    assert response == mock_response_data
    mistral_client_instance.client.post.assert_called_once()

@pytest.mark.asyncio
async def test_call_mistral_api_http_error(mistral_client_instance):
    """Test API call with HTTP status error."""
    mock_request = httpx.Request("POST", "http://test")
    real_httpx_response = httpx.Response(
        status_code=400,
        request=mock_request,
        content=b'{"detail": "Bad Request"}'
    )

    mock_http_error_response = AsyncMock(
        status_code=400,
        json=AsyncMock(return_value={"detail": "Bad Request"}),
        request=mock_request # Ensure the AsyncMock also has a request attribute
    )
    # Mock raise_for_status to raise the exception directly
    mock_http_error_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
        "Bad Request", request=mock_request, response=real_httpx_response
    ))
    mistral_client_instance.client.post.return_value = mock_http_error_response
    
    with pytest.raises(httpx.HTTPStatusError):
        await mistral_client_instance.call_mistral_api("/v1/chat/completions", {"prompt": "invalid"})
    # Assert that raise_for_status was called
    mistral_client_instance.client.post.return_value.raise_for_status.assert_called_once()

@pytest.mark.asyncio
async def test_call_mistral_api_request_error(mistral_client_instance):
    """Test API call with request error (e.g., network issue)."""
    mistral_client_instance.client.post.side_effect = httpx.RequestError("Network error", request=httpx.Request("POST", "http://test"))

    with pytest.raises(httpx.RequestError):
        await mistral_client_instance.call_mistral_api("/v1/chat/completions", {"prompt": "network"})

@pytest.mark.asyncio
async def test_call_mistral_api_retry_logic(mistral_client_instance):
    """Test retry logic for request errors."""
    settings.MISTRAL_MAX_RETRIES = 3
    settings.MISTRAL_RETRY_DELAY = 0.01 # Small delay for faster tests

    success_response = AsyncMock(
        status_code=200,
        json=AsyncMock(return_value={"choices": [{"message": {"content": "Success"}}]})
    )
    success_response.raise_for_status = Mock(return_value=None)

    mistral_client_instance.client.post.side_effect = [
        httpx.RequestError("Network error 1", request=httpx.Request("POST", "http://test")),
        httpx.RequestError("Network error 2", request=httpx.Request("POST", "http://test")),
        success_response
    ]

    response = await mistral_client_instance.call_mistral_api("/v1/chat/completions", {"prompt": "retry"})
    assert response["choices"][0]["message"]["content"] == "Success"
    assert mistral_client_instance.client.post.call_count == 3

@pytest.mark.asyncio
async def test_call_mistral_api_rate_limit_retry(mistral_client_instance):
    """
    TESTFALL_MC03: Test rate-limiting handling (429 error) with retry logic.
    """
    settings.MISTRAL_API_MAX_RETRIES = 3
    settings.MISTRAL_API_RETRY_DELAY = 0.01 # Small delay for faster tests

    rate_limit_error_response = AsyncMock(
        status_code=429,
        json=AsyncMock(return_value={"detail": "Rate limit exceeded"})
    )
    # Create a real httpx.Response for the HTTPStatusError
    mock_request = httpx.Request("POST", "http://test")
    real_httpx_response_429 = httpx.Response(
        status_code=429,
        request=mock_request,
        content=b'{"detail": "Rate limit exceeded"}'
    )
    rate_limit_error_response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
        "Rate limit exceeded", request=mock_request, response=real_httpx_response_429
    ))

    success_response_mock = AsyncMock(
        status_code=200,
        json=AsyncMock(return_value={"choices": [{"message": {"content": "Success after retry"}}]})
    )
    success_response_mock.raise_for_status = Mock(return_value=None)

    mistral_client_instance.client.post.side_effect = [
        httpx.HTTPStatusError("Rate limit exceeded", request=mock_request, response=real_httpx_response_429),
        httpx.HTTPStatusError("Rate limit exceeded", request=mock_request, response=real_httpx_response_429),
        success_response_mock # Success on the third attempt
    ]

    response = await mistral_client_instance.call_mistral_api("/v1/chat/completions", {"prompt": "rate_limit_retry"})
    assert response["choices"][0]["message"]["content"] == "Success after retry"
    assert mistral_client_instance.client.post.call_count == 3 # 2 retries + 1 success

@pytest.mark.asyncio
async def test_generate_pv_success(mistral_client_instance):
    """
    TESTFALL_MC01: Test PV generation with successful response and structure validation.
    """
    mock_pv_content = {
        "content": "Summary of the meeting.",
        "decisions": ["Decision A", "Decision B"],
        "actions": ["Action X (Responsible: Alice)", "Action Y (Responsible: Bob, Deadline: 2024-01-01)"]
    }
    mock_response_data = {"choices": [{"message": {"content": json.dumps(mock_pv_content)}}]}
    mock_http_response = AsyncMock(
        status_code=200,
        json=AsyncMock(return_value=mock_response_data)
    )
    mock_http_response.raise_for_status = Mock(return_value=None)
    mistral_client_instance.client.post.return_value = mock_http_response

    pv_content = await mistral_client_instance.generate_pv("meeting transcription")
    assert pv_content == mock_pv_content
    assert isinstance(pv_content, dict)
    assert "content" in pv_content and isinstance(pv_content["content"], str)
    assert "decisions" in pv_content and isinstance(pv_content["decisions"], list)
    assert "actions" in pv_content and isinstance(pv_content["actions"], list)
    mistral_client_instance.client.post.assert_called_once()
    expected_prompt_part = "Generate a structured \"Protokollvermerk\" (PV) from the following meeting transcription."
    assert expected_prompt_part in mistral_client_instance.client.post.call_args[1]['json']['messages'][0]['content']
    assert mistral_client_instance.client.post.call_args[1]['json']['response_format'] == {"type": "json_object"}

@pytest.mark.asyncio
async def test_extract_decisions_success(mistral_client_instance):
    """Test decision extraction with successful response."""
    mock_response_data = {"choices": [{"message": {"content": "Decision 1\nDecision 2"}}]}
    mock_http_response = AsyncMock(
        status_code=200,
        json=AsyncMock(return_value=mock_response_data)
    )
    mock_http_response.raise_for_status = Mock(return_value=None)
    mistral_client_instance.client.post.return_value = mock_http_response

    decisions = await mistral_client_instance.extract_decisions("meeting transcription")
    assert decisions == ["Decision 1", "Decision 2"]
    assert isinstance(decisions, list)
    assert all(isinstance(d, str) for d in decisions)
    mistral_client_instance.client.post.assert_called_once()
    expected_prompt_part = "From the following meeting transcription, extract all explicit decisions made."
    assert expected_prompt_part in mistral_client_instance.client.post.call_args[1]['json']['messages'][0]['content']

@pytest.mark.asyncio
async def test_extract_action_items_success(mistral_client_instance):
    """Test action item extraction with successful response."""
    mock_response_data = {"choices": [{"message": {"content": "Action 1\nAction 2"}}]}
    mock_http_response = AsyncMock(
        status_code=200,
        json=AsyncMock(return_value=mock_response_data)
    )
    mock_http_response.raise_for_status = Mock(return_value=None)
    mistral_client_instance.client.post.return_value = mock_http_response

    action_items = await mistral_client_instance.extract_action_items("meeting transcription")
    assert action_items == ["Action 1", "Action 2"]
    assert isinstance(action_items, list)
    assert all(isinstance(a, str) for a in action_items)
    mistral_client_instance.client.post.assert_called_once()
    expected_prompt_part = "From the following meeting transcription, extract all action items, including"
    assert expected_prompt_part in mistral_client_instance.client.post.call_args[1]['json']['messages'][0]['content']

@pytest.mark.asyncio
async def test_summarize_meeting_success(mistral_client_instance):
    """Test meeting summary generation with successful response."""
    mock_response_data = {"choices": [{"message": {"content": "Meeting summary"}}]}
    mock_http_response = AsyncMock(
        status_code=200,
        json=AsyncMock(return_value=mock_response_data)
    )
    mock_http_response.raise_for_status = Mock(return_value=None)
    mistral_client_instance.client.post.return_value = mock_http_response

    summary = await mistral_client_instance.summarize_meeting("meeting transcription")
    assert summary == "Meeting summary"
    mistral_client_instance.client.post.assert_called_once()
    expected_prompt_part = "Provide a concise summary of the following meeting transcription."
    assert expected_prompt_part in mistral_client_instance.client.post.call_args[1]['json']['messages'][0]['content']

def test_generate_prompt_valid_template(mistral_client_instance):
    """Test _generate_prompt with a valid template."""
    prompt = mistral_client_instance._generate_prompt("pv_generation", transcription="test_transcript")
    assert "Generate a \"Protokollvermerk\" (PV)" in prompt
    assert "test_transcript" in prompt

def test_generate_prompt_invalid_template_mc04(mistral_client_instance):
    """
    TESTFALL_MC04: Test _generate_prompt with an invalid template to ensure ValueError is raised.
    """
    with pytest.raises(ValueError, match="Unknown prompt template: invalid_template"):
        mistral_client_instance._generate_prompt("invalid_template", transcription="test")
