import asyncio
import httpx
from app.services.pv_service import PVService
from app.core.database import AsyncSessionLocal
from app.models.recording import Recording
from app.models.meeting import Meeting
from app.models.pv import PV
from app.models.action import Action
from app.models.transcription import Transcription
from app.core.config import settings
from sqlalchemy import select
import uuid

async def test_master_scenario():
    print("--- 🏆 MASTER SCENARIO TEST (MULTILINGUAL): STARTING ---")
    
    meeting_id = "test-meeting-123"
    # Multilingual text: French, Arabic (Tunisian), English
    transcription_text = """
    Sami: Bonjour tout le monde. Let's start our meeting.
    Amel: نحب نحكي على الـ Budget متاع 2026. On doit augmenter les ressources.
    Directeur General: C'est noté. We need a detailed plan for the IT department.
    Sami: D'accord. أنا باش نكلم الـ Banque غدوة pour finaliser le dossier.
    """

    async with AsyncSessionLocal() as db:
        # 1. Simulate Transcription Save
        print("💾 Step 1: Saving multilingual transcription...")
        db_transcription = Transcription(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            recording_id="rec-test-123", # Required by DB
            full_text=transcription_text,
            language="multi",
            status="completed"
        )
        db.add(db_transcription)
        await db.commit()
        print("✅ Multilingual Transcription saved.")

        # 2. Call Mistral (Real API Call with our new Prompt)
        print("🤖 Step 2: Calling Mistral (Multilingual Processing)...")
        try:
            pv_data = await PVService.generate_pv(transcription_text)
            print(f"✅ Mistral Response Title: {pv_data['title']}")
            print(f"📝 Summary Preview: {pv_data['summary'][:100]}...")
            
            # 3. Save PV to DB
            db_pv = PV(
                id=str(uuid.uuid4()),
                meeting_id=meeting_id,
                title=pv_data["title"],
                content_html=pv_data["summary"],
                status="validated",
                is_validated=True
            )
            db.add(db_pv)
            
            # 4. Save Actions
            for act in pv_data.get("actions", []):
                db_action = Action(
                    id=str(uuid.uuid4()),
                    meeting_id=meeting_id,
                    title=act["description"],
                    description=f"Assignee: {act.get('assignee', 'N/A')}. Reason: {act.get('priority_reason', 'N/A')}",
                    status="pending"
                )
                db.add(db_action)
                print(f"📌 Action Item created: {act['description']} (Assignee: {act.get('assignee')})")
            
            await db.commit()
            print("✅ PV and Actions saved to Database.")

            # 5. Trigger n8n Webhook
            print("✉️ Step 3: Notifying n8n for E-Mail dispatch...")
            payload = {
                "event": "transcription.completed",
                "meeting_id": meeting_id
            }
            try:
                async with httpx.AsyncClient() as client:
                    res = await client.post(settings.N8N_WEBHOOK_TRANSCRIPTION_COMPLETED, json=payload)
                    if res.status_code == 200:
                        print("✅ n8n notified successfully!")
                    else:
                        print(f"⚠️ n8n responded with {res.status_code} (Workflow likely not active)")
            except Exception as e:
                print(f"❌ n8n notification failed: {e}")

        except Exception as e:
            print(f"❌ Mistral API failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_master_scenario())
