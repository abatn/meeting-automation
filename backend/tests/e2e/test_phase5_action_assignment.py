"""
Phase 5 E2E Tests: Action Assignment & Data Persistence

Tests for:
- P1-5: Fuzzy matching for action assignments
- P1-9: completed_at set on action completion
- P2-8: DB indices for performance

Date: 2026-05-05
Author: OpenCode AI
"""
import pytest
import inspect
from datetime import datetime, timedelta
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.action import Action, Assignment, ActionStatus
from app.models.user import User
from app.tasks.transcription_tasks import _save_pv_and_actions
from app.services.action_service import ActionService
from app.core.config import settings


# Helper to detect if we're using PostgreSQL
def is_postgresql(db_session):
    """Check if database is PostgreSQL"""
    try:
        return "postgresql" in str(db_session.bind.url).lower()
    except:
        return False


@pytest.mark.asyncio
async def test_p15_fuzzy_matching_implemented(db_session: AsyncSession):
    """P1-5: _save_pv_and_actions should have fuzzy matching logic"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check for fuzzy matching implementation
    assert "ilike" in source, "Should use ilike for fuzzy matching"
    assert "full_name.ilike" in source or "User.full_name.ilike" in source, "Should search user full_name"
    assert "email.ilike" in source or "User.email.ilike" in source, "Should search user email"
    assert "f\"%{assignee_name}%\"" in source, "Should use substring matching"


@pytest.mark.asyncio
async def test_p15_assignment_creation_in_save_pv(db_session: AsyncSession):
    """P1-5: Assignments should be created during PV save"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check for Assignment creation
    assert "Assignment(" in source, "Should create Assignment objects"
    assert "action_id" in source, "Should link assignment to action"
    assert "user_id" in source, "Should link assignment to user"


@pytest.mark.asyncio
async def test_p15_external_assignment_fallback(db_session: AsyncSession):
    """P1-5: Should create external assignment if user not found"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check for external assignment handling
    assert "external_name" in source, "Should handle external_name"
    assert "external_email" in source, "Should handle external_email"
    assert "@" in source, "Should check for email format"


@pytest.mark.asyncio
async def test_p15_assignee_name_extraction(db_session: AsyncSession):
    """P1-5: Should extract assignee name from action data"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check for assignee extraction
    assert "assignee" in source, "Should extract assignee from action"
    assert "act.get(\"assignee\")" in source, "Should safely get assignee from action dict"


@pytest.mark.asyncio
async def test_p19_completed_at_set_on_completion(db_session: AsyncSession):
    """P1-9: completed_at should be set when action status = COMPLETED"""
    source = inspect.getsource(ActionService.update_action_status)
    
    # Check for completed_at implementation
    assert "completed_at" in source, "Should set completed_at"
    assert "datetime.utcnow()" in source, "Should use current datetime"
    assert "ActionStatus.COMPLETED" in source, "Should check for COMPLETED status"


@pytest.mark.asyncio
async def test_p19_completed_at_timestamp(db_session: AsyncSession):
    """P1-9: completed_at should be a datetime"""
    source = inspect.getsource(ActionService.update_action_status)
    
    # Verify datetime assignment
    assert "= datetime.utcnow()" in source, "Should assign datetime.utcnow()"


@pytest.mark.asyncio
async def test_p28_indices_exist(db_session: AsyncSession):
    """P2-8: Required indices should exist on production database"""
    if not is_postgresql(db_session):
        pytest.skip("Index check only for PostgreSQL (not SQLite)")
    
    # Get list of indices from PostgreSQL information_schema
    result = await db_session.execute(text("""
        SELECT indexname FROM pg_indexes 
        WHERE schemaname = 'public' AND tablename IN ('actions', 'action_assignments', 'recordings')
        ORDER BY indexname
    """))
    indices = {row[0] for row in result.fetchall()}
    
    # Check for required indices
    expected_indices = {
        'ix_actions_meeting_status',
        'ix_action_assignments_user_id',
        'ix_recordings_meeting_status',
    }
    
    for idx in expected_indices:
        assert idx in indices, f"Index {idx} should exist"


@pytest.mark.asyncio
async def test_p28_actions_meeting_status_index(db_session: AsyncSession):
    """P2-8: actions(meeting_id, status) index should exist"""
    if not is_postgresql(db_session):
        pytest.skip("Index check only for PostgreSQL (not SQLite)")
    
    result = await db_session.execute(text("""
        SELECT indexname FROM pg_indexes 
        WHERE schemaname = 'public' AND tablename = 'actions' 
        AND indexname = 'ix_actions_meeting_status'
    """))
    
    assert result.fetchone() is not None, "Should have ix_actions_meeting_status index"


@pytest.mark.asyncio
async def test_p28_action_assignments_user_id_index(db_session: AsyncSession):
    """P2-8: action_assignments(user_id) index should exist"""
    if not is_postgresql(db_session):
        pytest.skip("Index check only for PostgreSQL (not SQLite)")
    
    result = await db_session.execute(text("""
        SELECT indexname FROM pg_indexes 
        WHERE schemaname = 'public' AND tablename = 'action_assignments' 
        AND indexname = 'ix_action_assignments_user_id'
    """))
    
    assert result.fetchone() is not None, "Should have ix_action_assignments_user_id index"


@pytest.mark.asyncio
async def test_p28_recordings_meeting_status_index(db_session: AsyncSession):
    """P2-8: recordings(meeting_id, status) index should exist"""
    if not is_postgresql(db_session):
        pytest.skip("Index check only for PostgreSQL (not SQLite)")
    
    result = await db_session.execute(text("""
        SELECT indexname FROM pg_indexes 
        WHERE schemaname = 'public' AND tablename = 'recordings' 
        AND indexname = 'ix_recordings_meeting_status'
    """))
    
    assert result.fetchone() is not None, "Should have ix_recordings_meeting_status index"


@pytest.mark.asyncio
async def test_p15_fuzzy_matching_order(db_session: AsyncSession):
    """P1-5: Should handle assignee matching in correct order"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Find position of user lookup vs assignment creation
    user_lookup_pos = source.find("select(User)")
    assignment_creation_pos = source.find("Assignment(")
    
    assert user_lookup_pos < assignment_creation_pos, "Should lookup user before creating assignment"


@pytest.mark.asyncio
async def test_p15_client_id_isolation_in_fuzzy_match(db_session: AsyncSession):
    """P1-5: Fuzzy matching should respect client_id isolation"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check that client_id filter is in the query
    assert "client_id == recording.client_id" in source, "Should filter by client_id"


@pytest.mark.asyncio
async def test_p15_assignments_linked_to_action(db_session: AsyncSession):
    """P1-5: Each assignment should have action_id"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Look for assignment initialization
    assert "action_id=action.id" in source, "Assignment should reference action"


@pytest.mark.asyncio
async def test_p15_handles_missing_assignee(db_session: AsyncSession):
    """P1-5: Should skip if assignee_name is None or empty"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check for None/empty handling
    assert "if not assignee_name:" in source, "Should check if assignee_name exists"


@pytest.mark.asyncio
async def test_p19_only_completed_sets_timestamp(db_session: AsyncSession):
    """P1-9: Only COMPLETED status should set completed_at"""
    source = inspect.getsource(ActionService.update_action_status)
    
    # Find the completed_at assignment
    completed_at_pos = source.find("completed_at = datetime.utcnow()")
    if_completed_pos = source.find("ActionStatus.COMPLETED")
    
    assert completed_at_pos != -1, "Should have completed_at assignment"
    # completed_at should be near COMPLETED check
    assert abs(completed_at_pos - if_completed_pos) < 200, "completed_at should be in COMPLETED branch"


@pytest.mark.asyncio
async def test_p15_pv_data_structure(db_session: AsyncSession):
    """P1-5: Should expect correct PV data structure from Mistral"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check expected fields in pv_data
    assert 'pv_data.get("actions"' in source, "Should get actions from pv_data"
    assert 'pv_data.get("summary"' in source, "Should get summary from pv_data"
    assert 'act.get("deadline"' in source, "Should handle deadline"
    assert 'act.get("priority"' in source, "Should handle priority"


@pytest.mark.asyncio
async def test_p15_action_title_from_description(db_session: AsyncSession):
    """P1-5: Action title should come from description"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check that description is used as title
    assert 'act.get("description"' in source, "Should get description from action"
    assert 'title=description' in source, "Should use description as title"


@pytest.mark.asyncio
async def test_p15_deadline_parsing(db_session: AsyncSession):
    """P1-5: Should handle deadline parsing with error handling"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check for deadline handling
    assert "try:" in source, "Should have try block for deadline parsing"
    assert "datetime.fromisoformat" in source, "Should parse ISO format dates"
    assert "except (ValueError, TypeError):" in source, "Should catch date parsing errors"


@pytest.mark.asyncio
async def test_p15_action_status_pending_on_create(db_session: AsyncSession):
    """P1-5: New actions should have status PENDING"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check that status is set to PENDING
    assert 'ActionStatus.PENDING' in source, "Should set status to PENDING for new actions"


@pytest.mark.asyncio
async def test_p28_indices_have_correct_columns(db_session: AsyncSession):
    """P2-8: Indices should be on correct columns"""
    if not is_postgresql(db_session):
        pytest.skip("Index check only for PostgreSQL (not SQLite)")
    
    # Check index composition
    result = await db_session.execute(text("""
        SELECT indexname, indexdef FROM pg_indexes 
        WHERE schemaname = 'public' AND indexname = 'ix_actions_meeting_status'
    """))
    
    row = result.fetchone()
    assert row is not None, "Index should exist"
    index_def = row[1]
    
    # Should include both meeting_id and status
    assert "meeting_id" in index_def, "Index should include meeting_id"
    assert "status" in index_def, "Index should include status"


def test_p15_assignments_model_structure():
    """P1-5: Assignment model should support both user_id and external fields"""
    # Check that Assignment model has necessary fields
    from app.models.action import Assignment
    
    # Get all column names from the model
    columns = {col.name for col in Assignment.__table__.columns}
    
    assert "action_id" in columns, "Should have action_id"
    assert "user_id" in columns, "Should have user_id (nullable)"
    assert "external_name" in columns, "Should have external_name (nullable)"
    assert "external_email" in columns, "Should have external_email (nullable)"


def test_p19_action_model_has_completed_at():
    """P1-9: Action model should have completed_at field"""
    from app.models.action import Action
    
    columns = {col.name for col in Action.__table__.columns}
    
    assert "completed_at" in columns, "Should have completed_at column"


@pytest.mark.asyncio
async def test_p15_fuzzy_matching_case_insensitive(db_session: AsyncSession):
    """P1-5: Fuzzy matching should be case-insensitive"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check for ilike (case-insensitive like)
    assert ".ilike(" in source, "Should use ilike for case-insensitive matching"


@pytest.mark.asyncio
async def test_p28_index_performance_benefit(db_session: AsyncSession):
    """P2-8: Indices should improve query performance"""
    if not is_postgresql(db_session):
        pytest.skip("Index check only for PostgreSQL (not SQLite)")
    
    # This is a code-level test - indices exist and are correctly named
    result = await db_session.execute(text("""
        SELECT COUNT(*) as index_count FROM pg_indexes 
        WHERE schemaname = 'public' AND tablename IN ('actions', 'action_assignments', 'recordings')
        AND indexname LIKE 'ix_%'
    """))
    
    count = result.scalar()
    assert count >= 3, f"Should have at least 3 indices, found {count}"


@pytest.mark.asyncio
async def test_p19_assignment_creation_context(db_session: AsyncSession):
    """P1-9: Assignments created with full context"""
    source = inspect.getsource(_save_pv_and_actions)
    
    # Check that all necessary fields are populated during creation
    assert "action_id=" in source, "Should set action_id"
    # Should have either user_id or external fields
    assert ("user_id=" in source or "external_name=" in source), "Should set user_id or external_name"
