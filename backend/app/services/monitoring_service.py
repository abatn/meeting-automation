import os
import time
import logging
import asyncio
import boto3
import httpx
import re
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings, get_bucket_name
from app.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

class MonitoringService:
    
    @staticmethod
    async def get_container_metrics() -> Dict[str, Any]:
        """Fetch container metrics via Prometheus cadvisor"""
        metrics = {
            "frontend": {"cpu_percent": 0, "ram_mb": 0, "uptime_s": 0},
            "backend": {"cpu_percent": 0, "ram_mb": 0, "uptime_s": 0},
            "celery": {"cpu_percent": 0, "ram_mb": 0, "uptime_s": 0}
        }
        
        prom_url = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090"
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Query container CPU usage rate (5min average)
                cpu_resp = await client.get(
                    f"{prom_url}/api/v1/query",
                    params={"query": "sum by (pod) (rate(container_cpu_usage_seconds_total{namespace=\"meeting-automation-staging\", container!=\"\"}[5m])) * 100"}
                )
                # Query container memory working set
                mem_resp = await client.get(
                    f"{prom_url}/api/v1/query",
                    params={"query": "sum by (pod) (container_memory_working_set_bytes{namespace=\"meeting-automation-staging\", container!=\"\"}) / 1024 / 1024"}
                )
                # Query container uptime (start time)
                uptime_resp = await client.get(
                    f"{prom_url}/api/v1/query",
                    params={"query": "time() - container_start_time_seconds{namespace=\"meeting-automation-staging\", container!=\"\"}"}
                )
                
                def map_pod_to_service(pod_name: str) -> str:
                    if "frontend" in pod_name:
                        return "frontend"
                    elif "celery-worker" in pod_name or "celery_worker" in pod_name:
                        return "celery"
                    elif "backend" in pod_name:
                        return "backend"
                    return ""
                
                if cpu_resp.status_code == 200:
                    for result in cpu_resp.json().get("data", {}).get("result", []):
                        pod = result["metric"].get("pod", "")
                        service = map_pod_to_service(pod)
                        if service:
                            cpu_val = float(result["value"][1]) if result["value"][1] != "NaN" else 0.0
                            metrics[service]["cpu_percent"] = round(cpu_val, 2)
                
                if mem_resp.status_code == 200:
                    for result in mem_resp.json().get("data", {}).get("result", []):
                        pod = result["metric"].get("pod", "")
                        service = map_pod_to_service(pod)
                        if service:
                            mem_val = float(result["value"][1]) if result["value"][1] != "NaN" else 0.0
                            metrics[service]["ram_mb"] = round(mem_val, 1)
                
                if uptime_resp.status_code == 200:
                    for result in uptime_resp.json().get("data", {}).get("result", []):
                        pod = result["metric"].get("pod", "")
                        service = map_pod_to_service(pod)
                        if service:
                            uptime_val = float(result["value"][1]) if result["value"][1] != "NaN" else 0.0
                            metrics[service]["uptime_s"] = round(uptime_val, 0)
                            
        except Exception as e:
            logger.warning(f"Prometheus container metrics unavailable: {e}")
                
        return metrics

    @staticmethod
    async def get_database_metrics(db: AsyncSession) -> Dict[str, Any]:
        """Fetch PostgreSQL metrics including active connections, slow queries, and hit ratio"""
        metrics = {
            "status": "unhealthy", 
            "latency_ms": -1,
            "active_connections": 0,
            "slow_queries": 0,
            "cache_hit_ratio": 0.0
        }
        try:
            start_time = time.time()
            # Simple ping
            await db.execute(text("SELECT 1"))
            metrics["latency_ms"] = (time.time() - start_time) * 1000
            metrics["status"] = "healthy"
            
            # Active connections
            conn_res = await db.execute(text("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"))
            metrics["active_connections"] = conn_res.scalar() or 0
            
            # Slow queries (>100ms)
            slow_res = await db.execute(text("""
                SELECT count(*) 
                FROM pg_stat_activity 
                WHERE state = 'active' AND now() - query_start > interval '100 milliseconds';
            """))
            metrics["slow_queries"] = slow_res.scalar() or 0
            
            # Cache hit ratio
            cache_res = await db.execute(text("""
                SELECT 
                  sum(blks_hit) * 100 / nullif(sum(blks_hit) + sum(blks_read), 0) AS cache_hit_ratio
                FROM pg_stat_database;
            """))
            hit_ratio = cache_res.scalar()
            metrics["cache_hit_ratio"] = float(hit_ratio) if hit_ratio else 0.0
            
        except Exception as e:
            logger.error(f"DB Monitoring error: {e}")
            
        return metrics

    @staticmethod
    async def get_redis_metrics() -> Dict[str, Any]:
        """Fetch Redis metrics: Cache Hit Ratio, Memory Usage, Evicted Keys"""
        metrics = {
            "status": "unhealthy", 
            "latency_ms": -1,
            "hit_rate": 0.0,
            "memory_mb": 0.0,
            "memory_used": "0B",
            "evicted_keys": 0,
            "total_keys": 0,
            "version": "unknown",
            "uptime_seconds": 0
        }
        try:
            redis_start = time.time()
            r_client = await get_redis_client()
            await r_client.ping()
            metrics["latency_ms"] = (time.time() - redis_start) * 1000
            metrics["status"] = "healthy"
            
            # Stats (Hit rate & Evicted)
            info_stats = await r_client.info('stats')
            hits = int(info_stats.get('keyspace_hits', 0))
            misses = int(info_stats.get('keyspace_misses', 0))
            total = hits + misses
            metrics["hit_rate"] = (hits / total * 100) if total > 0 else 0.0
            metrics["evicted_keys"] = int(info_stats.get('evicted_keys', 0))
            
            # Memory
            info_memory = await r_client.info('memory')
            mem_bytes = info_memory.get('used_memory', 0)
            metrics["memory_mb"] = mem_bytes / (1024 * 1024)
            metrics["memory_used"] = info_memory.get('used_memory_human', f"{mem_bytes / (1024*1024):.1f}M")
            
            # Server info
            info_server = await r_client.info('server')
            metrics["version"] = info_server.get('redis_version', 'unknown')
            metrics["uptime_seconds"] = int(info_server.get('uptime_in_seconds', 0))
            
            # Keys
            info_keyspace = await r_client.info('keyspace')
            for db_key, db_info in info_keyspace.items():
                if db_key.startswith('db'):
                    metrics["total_keys"] += int(db_info.get('keys', 0))
            
        except Exception as e:
            logger.error(f"Redis Monitoring error: {e}")
            
        return metrics

    @staticmethod
    async def get_minio_metrics() -> Dict[str, Any]:
        """Fetch MinIO storage and object count"""
        metrics = {
            "status": "unhealthy",
            "usage_mb": 0.0,
            "object_count": 0
        }
        try:
            # Prefer using CloudWatch/MinIO Prometheus metrics if available, but boto3 is simple
            s3 = boto3.client(
                's3',
                endpoint_url=settings.S3_ENDPOINT,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
            )
            
            # To avoid iterating all objects which is slow, we use list_objects_v2
            # For production, MinIO prometheus endpoint /minio/v2/metrics/cluster is better
            # but requires auth. Using basic iteration here since it's a prototype/small deployment.
            total_size = 0
            total_objects = 0
            
            paginator = s3.get_paginator('list_objects_v2')
            try:
                for page in paginator.paginate(Bucket=get_bucket_name()):
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            total_size += obj['Size']
                            total_objects += 1
                
                metrics["usage_mb"] = total_size / (1024 * 1024)
                metrics["object_count"] = total_objects
                metrics["status"] = "healthy"
            except Exception as e:
                logger.error(f"MinIO bucket error: {e}")
        except Exception as e:
            logger.error(f"MinIO connection error: {e}")
            
        return metrics

    @staticmethod
    async def get_rabbitmq_metrics() -> Dict[str, Any]:
        """Fetch RabbitMQ queue trends and unacknowledged messages"""
        metrics = {
            "status": "unhealthy",
            "queues": [],
            "total_unacked": 0
        }
        try:
            rabbit_user, rabbit_pass = "rabbit_user", "rabbit_password"
            match = re.search(r"amqp://([^:]+):([^@]+)@", settings.CELERY_BROKER_URL)
            if match:
                rabbit_user, rabbit_pass = match.groups()

            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(
                    "http://rabbitmq-staging:15672/api/queues/", 
                    auth=(rabbit_user, rabbit_pass)
                )
                if r.status_code == 200:
                    metrics["status"] = "healthy"
                    total_unacked = 0
                    for q in r.json():
                        unacked = q.get("messages_unacknowledged", 0)
                        total_unacked += unacked
                        
                        queue_data = {
                            "name": q.get("name"),
                            "messages": q.get("messages", 0),
                            "unacked": unacked,
                            "consumers": q.get("consumers", 0)
                        }
                        metrics["queues"].append(queue_data)
                    
                    metrics["total_unacked"] = total_unacked
                    
                    # Store trend in Redis for the last 60 minutes
                    r_client = await get_redis_client()
                    timestamp = int(time.time())
                    
                    # Just an example of storing trends: LPUSH then LTRIM to keep 60
                    await r_client.lpush("rmq:trend:total_msgs", f"{timestamp}:{sum(q['messages'] for q in metrics['queues'])}")
                    await r_client.ltrim("rmq:trend:total_msgs", 0, 59)
                    
                    await r_client.lpush("rmq:trend:unacked", f"{timestamp}:{total_unacked}")
                    await r_client.ltrim("rmq:trend:unacked", 0, 59)
                    
        except Exception as e:
            logger.error(f"RabbitMQ check failed: {e}")
            
        return metrics

    @staticmethod
    async def get_ai_metrics() -> Dict[str, Any]:
        """Fetch AI Response Times and Error Rates"""
        # Read from Redis where the AI services store their metrics
        metrics = {
            "mistral": {"status": "unknown", "avg_latency_s": 0.0, "error_rate": 0.0},
            "gladia": {"status": "unknown", "avg_latency_s": 0.0, "error_rate": 0.0}
        }
        
        try:
            r_client = await get_redis_client()
            
            # Mistral
            m_latencies = await r_client.lrange("ai:mistral:latencies", 0, 100)
            m_errors = int(await r_client.get("ai:mistral:errors") or 0)
            m_calls = int(await r_client.get("ai:mistral:calls") or 0)
            
            if m_latencies:
                avg_lat = sum(float(l) for l in m_latencies) / len(m_latencies)
                metrics["mistral"]["avg_latency_s"] = avg_lat
                metrics["mistral"]["status"] = "healthy"
            if m_calls > 0:
                metrics["mistral"]["error_rate"] = (m_errors / m_calls) * 100
                
            # Gladia
            g_latencies = await r_client.lrange("ai:gladia:latencies", 0, 100)
            g_errors = int(await r_client.get("ai:gladia:errors") or 0)
            g_calls = int(await r_client.get("ai:gladia:calls") or 0)
            
            if g_latencies:
                avg_lat = sum(float(l) for l in g_latencies) / len(g_latencies)
                metrics["gladia"]["avg_latency_s"] = avg_lat
                metrics["gladia"]["status"] = "healthy"
            if g_calls > 0:
                metrics["gladia"]["error_rate"] = (g_errors / g_calls) * 100
                
        except Exception as e:
            logger.error(f"AI Metrics error: {e}")
            
        return metrics

    @staticmethod
    async def get_n8n_metrics() -> Dict[str, Any]:
        n8n_status = "unknown"
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get("http://n8n-staging:5678/healthz")
                if r.status_code == 200:
                    n8n_status = "healthy"
                else:
                    n8n_status = f"unhealthy ({r.status_code})"
        except Exception:
            n8n_status = "unhealthy"
        
        return {"status": n8n_status}
