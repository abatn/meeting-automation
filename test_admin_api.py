import asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

async def test_endpoint():
    from app.services.monitoring_service import MonitoringService
    engine = create_async_engine("postgresql+asyncpg://meeting_user:meeting_password@localhost:5432/meeting_db")
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session() as session:
        # We just test the metrics gathering function directly
        res = await asyncio.gather(
            MonitoringService.get_container_metrics(),
            MonitoringService.get_database_metrics(session),
            MonitoringService.get_redis_metrics(),
            MonitoringService.get_minio_metrics(),
            MonitoringService.get_rabbitmq_metrics(),
            MonitoringService.get_ai_metrics(),
            MonitoringService.get_n8n_metrics()
        )
        print("Success:", res)

asyncio.run(test_endpoint())
