import pytest
import uuid
import json
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.meeting import Meeting
from app.models.pv import PV

@pytest.mark.asyncio
async def test_pv_versioning_lifecycle(client: AsyncClient, db_session: AsyncSession):
    # 1. Setup Mock Meeting & PV in DB
    meeting_id = str(uuid.uuid4())
    pv_id = str(uuid.uuid4())
    
    mock_meeting = Meeting(
        id=meeting_id,
        title="Test Meeting for PV",
        start_time=datetime(2026, 3, 1, 10, 0, 0),
        end_time=datetime(2026, 3, 1, 11, 0, 0),
        location="Virtual",
        creator_id="test-user-id"
    )
    db_session.add(mock_meeting)
    
    mock_pv = PV(
        id=pv_id,
        meeting_id=meeting_id,
        title="Original PV Title",
        content_html="<p>Initial content</p>",
        status="draft"
    )
    db_session.add(mock_pv)
    await db_session.commit()
    
    # 2. Update PV (Should trigger creation of Version 1)
    update_data = {
        "title": "Updated PV Title",
        "content_html": "<p>Updated content</p>",
        "status": "pending_review"
    }
    
    update_response = await client.put(f"/api/v1/pv/{pv_id}", json=update_data)
    assert update_response.status_code == 200
    assert update_response.json()["version_created"] == 1
    
    # 3. Check if Version 1 is listed and contains the Original Snapshot
    versions_response = await client.get(f"/api/v1/pv/{pv_id}/versions")
    assert versions_response.status_code == 200
    versions = versions_response.json()
    assert len(versions) == 1
    
    version_1 = versions[0]
    assert version_1["version_number"] == 1
    
    snapshot_data = json.loads(version_1["snapshot_data"])
    assert snapshot_data["title"] == "Original PV Title"
    assert snapshot_data["content_html"] == "<p>Initial content</p>"
    
    version_id = version_1["id"]
    
    # 4. Get specific version
    single_version_response = await client.get(f"/api/v1/pv/{pv_id}/versions/{version_id}")
    assert single_version_response.status_code == 200
    assert single_version_response.json()["version_number"] == 1
    
    # 5. Restore PV to Version 1
    restore_response = await client.post(f"/api/v1/pv/{pv_id}/restore/{version_id}")
    assert restore_response.status_code == 200
    
    # 6. Verify PV was restored to Original State
    pv_response = await client.get(f"/api/v1/pv/{pv_id}")
    assert pv_response.status_code == 200
    restored_pv = pv_response.json()
    assert restored_pv["content"] == "<p>Initial content</p>"
    
    # 7. Verify a Backup Version (Version 2) was created automatically before restore
    final_versions_response = await client.get(f"/api/v1/pv/{pv_id}/versions")
    final_versions = final_versions_response.json()
    assert len(final_versions) == 2
    assert final_versions[0]["version_number"] == 2 # Ordered by desc
