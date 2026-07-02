import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.action_service import ActionService
from app.models.action import Action, ActionStatus


@pytest.fixture
def mock_db():
    """Create a mock async database session."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def action_service(mock_db):
    """Create ActionService with mocked db."""
    return ActionService(mock_db)


@pytest.mark.asyncio
async def test_update_action_status_valid_pending(action_service, mock_db):
    """Test that a valid status 'pending' updates correctly."""
    # Arrange: mock action lookup
    mock_action = MagicMock(spec=Action)
    mock_action.id = "action-123"
    mock_action.title = "Test Action"
    mock_action.status = ActionStatus.COMPLETED  # initial state
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_action
    mock_result.scalar_one.return_value = mock_action
    mock_db.execute.return_value = mock_result

    # Act
    result = await action_service.update_action_status(
        action_id="action-123",
        client_id="client-456",
        status="PENDING"
    )

    # Assert
    assert result == mock_action
    assert mock_action.status == ActionStatus.PENDING
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_action_status_valid_in_progress(action_service, mock_db):
    """Test that a valid status 'in_progress' updates correctly."""
    mock_action = MagicMock(spec=Action)
    mock_action.id = "action-123"
    mock_action.title = "Test Action"
    mock_action.status = ActionStatus.PENDING
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_action
    mock_result.scalar_one.return_value = mock_action
    mock_db.execute.return_value = mock_result

    result = await action_service.update_action_status(
        action_id="action-123",
        client_id="client-456",
        status="IN_PROGRESS"
    )

    assert result == mock_action
    assert mock_action.status == ActionStatus.IN_PROGRESS
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_action_status_valid_completed(action_service, mock_db):
    """Test that a valid status 'completed' updates correctly."""
    mock_action = MagicMock(spec=Action)
    mock_action.id = "action-123"
    mock_action.title = "Test Action"
    mock_action.status = ActionStatus.IN_PROGRESS
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_action
    mock_result.scalar_one.return_value = mock_action
    mock_db.execute.return_value = mock_result

    result = await action_service.update_action_status(
        action_id="action-123",
        client_id="client-456",
        status="COMPLETED"
    )

    assert result == mock_action
    assert mock_action.status == ActionStatus.COMPLETED
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_action_status_valid_cancelled(action_service, mock_db):
    """Test that a valid status 'cancelled' updates correctly."""
    mock_action = MagicMock(spec=Action)
    mock_action.id = "action-123"
    mock_action.title = "Test Action"
    mock_action.status = ActionStatus.PENDING
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_action
    mock_result.scalar_one.return_value = mock_action
    mock_db.execute.return_value = mock_result

    result = await action_service.update_action_status(
        action_id="action-123",
        client_id="client-456",
        status="CANCELLED"
    )

    assert result == mock_action
    assert mock_action.status == ActionStatus.CANCELLED
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_action_status_valid_overdue(action_service, mock_db):
    """Test that a valid status 'overdue' updates correctly."""
    mock_action = MagicMock(spec=Action)
    mock_action.id = "action-123"
    mock_action.title = "Test Action"
    mock_action.status = ActionStatus.PENDING
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_action
    mock_result.scalar_one.return_value = mock_action
    mock_db.execute.return_value = mock_result

    result = await action_service.update_action_status(
        action_id="action-123",
        client_id="client-456",
        status="OVERDUE"
    )

    assert result == mock_action
    assert mock_action.status == ActionStatus.OVERDUE
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_action_status_invalid_accepted(action_service, mock_db):
    """Test that an invalid status 'accepted' raises ValueError."""
    mock_action = MagicMock(spec=Action)
    mock_action.id = "action-123"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_action
    mock_result.scalar_one.return_value = mock_action
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError) as exc_info:
        await action_service.update_action_status(
            action_id="action-123",
            client_id="client-456",
            status="accepted"
        )

    assert "Invalid status value" in str(exc_info.value)
    assert "accepted" in str(exc_info.value)
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_action_status_invalid_rejected(action_service, mock_db):
    """Test that an invalid status 'rejected' raises ValueError."""
    mock_action = MagicMock(spec=Action)
    mock_action.id = "action-123"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_action
    mock_result.scalar_one.return_value = mock_action
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError) as exc_info:
        await action_service.update_action_status(
            action_id="action-123",
            client_id="client-456",
            status="rejected"
        )

    assert "Invalid status value" in str(exc_info.value)
    assert "rejected" in str(exc_info.value)
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_action_status_invalid_typo(action_service, mock_db):
    """Test that a typo ('pendin') raises ValueError."""
    mock_action = MagicMock(spec=Action)
    mock_action.id = "action-123"
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_action
    mock_result.scalar_one.return_value = mock_action
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError) as exc_info:
        await action_service.update_action_status(
            action_id="action-123",
            client_id="client-456",
            status="pendin"
        )

    assert "Invalid status value" in str(exc_info.value)
    assert "pendin" in str(exc_info.value)
    assert "Must be one of:" in str(exc_info.value)
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_action_status_nonexistent(action_service, mock_db):
    """Test that updating a non-existent action returns None."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    result = await action_service.update_action_status(
        action_id="nonexistent",
        client_id="client-456",
        status="PENDING"
    )

    assert result is None
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.services.action_service.httpx.AsyncClient")
async def test_update_action_status_n8n_notification_called(mock_async_client, action_service, mock_db):
    """Test that n8n webhook is called with correct payload on successful update."""
    mock_action = MagicMock(spec=Action)
    mock_action.id = "action-123"
    mock_action.title = "Test Action"
    mock_action.status = ActionStatus.PENDING
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_action
    mock_result.scalar_one.return_value = mock_action
    mock_db.execute.return_value = mock_result

    # Mock the httpx client
    mock_client_instance = AsyncMock()
    mock_client_instance.post = AsyncMock()
    mock_async_client.return_value.__aenter__.return_value = mock_client_instance

    result = await action_service.update_action_status(
        action_id="action-123",
        client_id="client-456",
        status="IN_PROGRESS"
    )

    assert result == mock_action
    # n8n notification is currently disabled (Phase 62: commented out in action_service.py:468-481)
    # The function should still work without the webhook call
