"""
End-to-End tests for user invitation workflow.
Tests the complete flow from user invitation through activation and login.

This test file requires:
- PostgreSQL database (specified in TEST_DATABASE_URL in conftest.py via E2E_TEST env)
- Running backend (uvicorn)
- All database migrations applied
"""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from httpx import AsyncClient
import secrets

from app.models.user import User, UserStatus, ActivationToken
from app.models.client import Client, SubscriptionStatus
from app.core.security import get_password_hash, verify_password


@pytest.mark.asyncio
class TestInvitationE2E:
    """End-to-end tests for the complete invitation workflow."""

    async def test_complete_invitation_flow(self, client: AsyncClient, db_session):
        """
        Test complete invitation flow:
        1. Create a pending user (simulating invitation)
        2. Verify the activation token
        3. Confirm activation with password
        4. Login with the new credentials
        """
        # Step 1: Create a PENDING user (simulating an invite)
        new_email = f"newinviteduser-{uuid.uuid4().hex[:8]}@example.com"
        new_user_id = str(uuid.uuid4())

        user = User(
            id=new_user_id,
            client_id="test-client-id",
            email=new_email,
            hashed_password=get_password_hash("TempPassword123!"),
            status=UserStatus.PENDING.value,
            full_name="New Invited User",
            is_superuser=False,
        )
        db_session.add(user)
        await db_session.flush()

        # Create activation token
        plaintext_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=48)

        activation_token = ActivationToken(
            id=str(uuid.uuid4()),
            user_id=new_user_id,
            token=plaintext_token,
            expires_at=expires_at,
        )
        db_session.add(activation_token)
        await db_session.commit()

        # Step 2: Verify the activation token
        verify_response = await client.get(
            f"/api/v1/auth/activate/verify?token={plaintext_token}"
        )

        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        assert verify_data["email"] == new_email

        # Step 3: Confirm activation with new password
        new_secure_password = "NewSecurePassword123!"
        confirm_response = await client.post(
            "/api/v1/auth/activate/confirm",
            json={
                "token": plaintext_token,
                "new_password": new_secure_password,
            },
        )

        assert confirm_response.status_code == 200
        confirm_data = confirm_response.json()
        # NEW: Should return user data and token_type (token is in httpOnly cookie)
        assert confirm_data["token_type"].lower() == "bearer"
        assert "user" in confirm_data, "Response should contain user data"
        assert confirm_data["user"]["email"] == new_email

        # Verify user is now ACTIVE
        user_result = await db_session.execute(
            select(User).where(User.id == new_user_id)
        )
        updated_user = user_result.scalar_one_or_none()
        assert updated_user is not None
        assert updated_user.status == UserStatus.ACTIVE.value
        assert verify_password(new_secure_password, updated_user.hashed_password)

        # Verify token was deleted
        token_result = await db_session.execute(
            select(ActivationToken).where(ActivationToken.user_id == new_user_id)
        )
        assert token_result.scalar_one_or_none() is None

        # Step 4: Login with new credentials
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": new_email,
                "password": new_secure_password,
            },
        )

        assert login_response.status_code == 200
        login_data = login_response.json()
        assert login_data["token_type"].lower() == "bearer"
        assert "accessToken" in login_response.cookies, "Login should set accessToken cookie"

    async def test_expired_token_cannot_be_used(
        self, client: AsyncClient, db_session
    ):
        """Test that expired tokens cannot be used for activation."""
        # Create a PENDING user
        expired_user_id = str(uuid.uuid4())
        user = User(
            id=expired_user_id,
            client_id="test-client-id",
            email=f"expiredtoken-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("TempPassword123!"),
            status=UserStatus.PENDING.value,
            is_superuser=False,
        )
        db_session.add(user)
        await db_session.flush()

        # Create EXPIRED token (already past expiry)
        plaintext_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        expired_token = ActivationToken(
            id=str(uuid.uuid4()),
            user_id=expired_user_id,
            token=plaintext_token,
            expires_at=expires_at,
        )
        db_session.add(expired_token)
        await db_session.commit()

        # Try to verify expired token
        verify_response = await client.get(
            f"/api/v1/auth/activate/verify?token={plaintext_token}"
        )

        assert verify_response.status_code == 400
        assert "expired" in verify_response.json()["detail"].lower()

        # Try to confirm with expired token
        confirm_response = await client.post(
            "/api/v1/auth/activate/confirm",
            json={
                "token": plaintext_token,
                "new_password": "NewPassword123!",
            },
        )

        assert confirm_response.status_code == 400
        assert "expired" in confirm_response.json()["detail"].lower()

    async def test_invalid_token_rejected(self, client: AsyncClient):
        """Test that invalid tokens are rejected."""
        # Try to verify random invalid token
        verify_response = await client.get(
            "/api/v1/auth/activate/verify?token=this-is-not-a-valid-token"
        )

        assert verify_response.status_code == 400
        assert "Invalid" in verify_response.json()["detail"]

        # Try to confirm with invalid token
        confirm_response = await client.post(
            "/api/v1/auth/activate/confirm",
            json={
                "token": "invalid-token",
                "new_password": "NewPassword123!",
            },
        )

        assert confirm_response.status_code == 400
        assert "Invalid" in confirm_response.json()["detail"]

    async def test_double_activation_prevented(
        self, client: AsyncClient, db_session
    ):
        """Test that a token cannot be used twice for activation."""
        # Create PENDING user with activation token
        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            client_id="test-client-id",
            email=f"doubleactivate-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=get_password_hash("TempPassword123!"),
            status=UserStatus.PENDING.value,
            is_superuser=False,
        )
        db_session.add(user)
        await db_session.flush()

        plaintext_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=48)

        activation_token = ActivationToken(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token=plaintext_token,
            expires_at=expires_at,
        )
        db_session.add(activation_token)
        await db_session.commit()

        # First activation should succeed and return JWT
        first_confirm = await client.post(
            "/api/v1/auth/activate/confirm",
            json={
                "token": plaintext_token,
                "new_password": "FirstPassword123!",
            },
        )

        assert first_confirm.status_code == 200
        first_confirm_data = first_confirm.json()
        # Should return token_type and user (token is in httpOnly cookie)
        assert first_confirm_data["token_type"].lower() == "bearer"
        assert "user" in first_confirm_data

        # Second activation with same token should fail (token deleted)
        second_confirm = await client.post(
            "/api/v1/auth/activate/confirm",
            json={
                "token": plaintext_token,
                "new_password": "SecondPassword123!",
            },
        )

        # Either 400 (invalid token) or 429 (rate limit hit in tests)
        assert second_confirm.status_code in [400, 429], f"Expected 400 or 429, got {second_confirm.status_code}"
        if second_confirm.status_code == 400:
            assert "Invalid" in second_confirm.json()["detail"]

        # Verify user still has first password, not second
        user_result = await db_session.execute(
            select(User).where(User.id == user_id)
        )
        final_user = user_result.scalar_one_or_none()
        assert verify_password("FirstPassword123!", final_user.hashed_password)
        assert not verify_password("SecondPassword123!", final_user.hashed_password)

    async def test_pending_user_cannot_login(
        self, client: AsyncClient, db_session
    ):
        """Test that PENDING users cannot login even with correct password."""
        # Create PENDING user
        pending_id = str(uuid.uuid4())
        pending_email = f"pendinglogin-{uuid.uuid4().hex[:8]}@example.com"
        pending_password = "CorrectPassword123!"

        user = User(
            id=pending_id,
            client_id="test-client-id",
            email=pending_email,
            hashed_password=get_password_hash(pending_password),
            status=UserStatus.PENDING.value,
            is_superuser=False,
        )
        db_session.add(user)
        await db_session.commit()

        # Try to login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": pending_email,
                "password": pending_password,
            },
        )

        assert login_response.status_code == 400
        assert "Inactive" in login_response.json()["detail"]
