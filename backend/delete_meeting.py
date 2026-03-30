import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import delete
from app.models.meeting import Meeting

async def run_delete():
    async with AsyncSessionLocal() as db:
        res = await db.execute(delete(Meeting).where(Meeting.title == 'Master Pipeline Test (Gladia & Mistral)'))
        await db.commit()
        print(f'Deleted {res.rowcount} meetings.')

if __name__ == '__main__':
    asyncio.run(run_delete())
