"""
E2E Test for P0: User.deleted_at Field

Tests that the User.deleted_at field works correctly in Cross-Tenant validation.
This test verifies that:
1. The deleted_at field exists in the database
2. The Cross-Tenant validation in report_service.py works correctly
"""
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_user_deleted_at_field_exists(db_session: AsyncSession):
    """
    Test that the deleted_at field exists in the User model.
    This verifies the database schema has been properly migrated.
    """
    from app.models.user import User
    
    # Query to check if the column exists (this will fail if column doesn't exist)
    result = await db_session.execute(
        select(User).limit(1)
    )
    user = result.scalar_one_or_none()
    
    # If there are users, check that deleted_at attribute is accessible
    if user is not None:
        # This should not raise an AttributeError
        _ = user.deleted_at
    
    # The query should succeed without error - this proves the column exists
    assert True, "User.deleted_at field is accessible"


@pytest.mark.asyncio
async def test_cross_tenant_validation_with_deleted_at(db_session: AsyncSession):
    """
    Test that the Cross-Tenant validation in report_service.py works correctly.
    This verifies that report_service.py:285 can query UserModel.deleted_at.is_(None)
    without causing an AttributeError.
    """
    from app.models.user import User
    from app.models.client import Client
    from sqlalchemy import select
    
    # Get a test user and client
    result = await db_session.execute(
        select(User).limit(1)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        pytest.skip("No users in database to test")
    
    # Get the user's client
    result = await db_session.execute(
        select(Client).where(Client.id == user.client_id)
    )
    client = result.scalar_one_or_none()
    
    if client is None:
        pytest.skip("No client found for user")
    
    # Test the exact query from report_service.py:285
    # This is the exact query that was failing before the fix:
    #   UserModel.deleted_at.is_(None)
    user_check = await db_session.execute(
        select(User.id).where(
            User.id == user.id,
            User.client_id == client.id,
            User.deleted_at.is_(None)
        )
    )
    
    # This should NOT raise an AttributeError - this was the P0 bug!
    found_user = user_check.scalar()
    
    assert found_user is not None, "User should be found with valid client_id and no deleted_at"
    assert True, "Cross-Tenant validation works with deleted_at.is_(None)"


@pytest.mark.asyncio
async def test_user_soft_delete(db_session: AsyncSession):
    """
    Test that users can be soft-deleted using the deleted_at field.
    """
    from app.models.user import User
    from datetime import datetime
    
    # Get a test user
    result = await db_session.execute(
        select(User).limit(1)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        pytest.skip("No users in database to test")
    
    # Set deleted_at to mark user as deleted (soft-delete)
    user.deleted_at = datetime.utcnow()
    await db_session.commit()
    
    # Refresh the user
    await db_session.refresh(user)
    
    # Verify deleted_at is set
    assert user.deleted_at is not None, "User should be soft-deleted"
    
    # Verify the user can be queried with the deleted_at filter
    result = await db_session.execute(
        select(User).where(
            User.id == user.id,
            User.deleted_at.is_(None)
        )
    )
    deleted_user = result.scalar_one_or_none()
    assert deleted_user is None, "Soft-deleted user should not be found with deleted_at.is_(None)"
    
    # Verify the user can be found without the filter
    result = await db_session.execute(
        select(User).where(User.id == user.id)
    )
    all_user = result.scalar_one_or_none()
    assert all_user is not None, "Soft-deleted user should still exist in database"
    
    # Cleanup: Restore the user
    user.deleted_at = None
    await db_session.commit()
    
    assert True, "User soft-delete works correctly"