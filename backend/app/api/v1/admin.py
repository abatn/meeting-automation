from typing import Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.api import deps
from app.models.user import User as UserModel, UserRole
from app.models.client import Client as ClientModel, SubscriptionStatus, SubscriptionPlan
from app.models.usage_minute import UsageMinute
from app.models.cms import PricingPlan
from app.schemas.client import Client, ClientUpdate
from app.services.audit_service import AuditService

router = APIRouter()

# Schema for status update
class StatusUpdate(BaseModel):
    status: SubscriptionStatus

# Security Dependency: Use unified get_current_system_admin from deps (A.5.17 ISO 27001)

@router.get("/clients", response_model=List[dict])
async def list_all_clients(
    status: Optional[SubscriptionStatus] = None,
    plan: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(deps.get_current_system_admin),
) -> Any:
    """
    Retrieve all clients with usage stats (System Admin only).
    """
    stmt = select(ClientModel)
    
    if status:
        stmt = stmt.where(ClientModel.subscription_status == status)
    if plan:
        stmt = stmt.where(ClientModel.subscription_plan == plan)
        
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    clients = result.scalars().all()
    
    # Enrich with current month usage
    period = datetime.now().strftime("%Y-%m")
    enriched_clients = []
    
    for c in clients:
        usage_stmt = select(func.sum(UsageMinute.minutes)).where(
            UsageMinute.client_id == c.id,
            UsageMinute.period == period
        )
        usage_res = await db.execute(usage_stmt)
        monthly_mins = usage_res.scalar() or 0
        
        c_dict = {
            "id": c.id,
            "company_name": c.company_name,
            "subscription_plan": c.subscription_plan,
            "subscription_status": c.subscription_status,
            "minutes_included": c.minutes_included,
            "minutes_used_total": c.minutes_used or 0,
            "minutes_used_month": monthly_mins,
            "created_at": c.created_at
        }
        enriched_clients.append(c_dict)
        
    return enriched_clients


@router.get("/clients/{client_id}", response_model=Client)
async def get_client_details(
    client_id: str,
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(deps.get_current_system_admin),
) -> Any:
    """
    Retrieve details of a specific client.
    """
    stmt = select(ClientModel).where(ClientModel.id == client_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    return client


@router.patch("/clients/{client_id}/status", response_model=Client)
async def update_client_status(
    client_id: str,
    status_update: StatusUpdate,
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(deps.get_current_system_admin),
) -> Any:
    """
    Activate, disable, or set a client to pending.
    """
    stmt = select(ClientModel).where(ClientModel.id == client_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    old_status = client.subscription_status
    client.subscription_status = status_update.status
    db.add(client)
    await db.commit()
    await db.refresh(client)
    
    # Log to Audit Trail
    await AuditService.log_action(
        db=db,
        client_id=client_id,
        user_id=admin.id,
        action="UPDATE_CLIENT_STATUS",
        table_name="clients",
        record_id=client_id,
        old_values={"status": old_status},
        new_values={"status": status_update.status}
    )
    
    return client


@router.post("/clients/{client_id}/observations", response_model=Client)
async def add_client_observation(
    client_id: str,
    observation: dict, # {"text": "Note to add"}
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(deps.get_current_system_admin),
) -> Any:
    """
    Add an internal note/observation to a client.
    """
    stmt = select(ClientModel).where(ClientModel.id == client_id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
        
    new_note = observation.get("text", "")
    if client.observations:
        client.observations += f"\n--- [{admin.email}] ---\n{new_note}"
    else:
        client.observations = f"--- [{admin.email}] ---\n{new_note}"
        
    db.add(client)
    await db.commit()
    await db.refresh(client)
    
    return client


@router.get("/revenue", response_model=dict)
async def get_revenue_statistics(
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(deps.get_current_system_admin),
) -> Any:
    """
    Get system-wide revenue and client statistics.
    """
    # 1. Client counts by status
    status_stmt = select(ClientModel.subscription_status, func.count(ClientModel.id)).group_by(ClientModel.subscription_status)
    status_result = await db.execute(status_stmt)
    status_counts = {str(s.name if hasattr(s, 'name') else s): count for s, count in status_result.all()}
    
    # 2. Client counts by plan (only ACTIVE clients)
    plan_stmt = (
        select(ClientModel.subscription_plan, func.count(ClientModel.id))
        .where(ClientModel.subscription_status == SubscriptionStatus.ACTIVE)
        .group_by(ClientModel.subscription_plan)
    )
    plan_result = await db.execute(plan_stmt)
    plan_counts = {str(p.name if hasattr(p, 'name') else p): count for p, count in plan_result.all()}
    
    # 3. Get prices from CMS pricing_plans (fallback to defaults)
    prices = {}
    for plan_code in ["PRO", "ENTREPRISE"]:
        price_stmt = select(PricingPlan.price_monthly).where(PricingPlan.plan_code == plan_code, PricingPlan.is_active == True)
        price_result = await db.execute(price_stmt)
        price_row = price_result.scalar_one_or_none()
        prices[plan_code] = price_row if price_row else (99 if plan_code == "PRO" else 499)
    
    # 4. Calculate Estimated Monthly Revenue (only ACTIVE clients)
    revenue = 0
    active_pro = plan_counts.get("PRO", 0)
    active_enterprise = plan_counts.get("ENTREPRISE", 0)
    
    revenue += active_pro * prices["PRO"]
    revenue += active_enterprise * prices["ENTREPRISE"]
    
    return {
        "total_clients": sum(status_counts.values()),
        "status_distribution": status_counts,
        "plan_distribution": plan_counts,
        "estimated_mrr_usd": revenue,
    }

@router.get("/system/performance", response_model=dict)
async def get_system_performance(
    db: AsyncSession = Depends(deps.get_db),
    admin: UserModel = Depends(deps.get_current_system_admin),
) -> Any:
    """
    Get system health and performance metrics (System Admin only).
    """
    import time
    from app.services.monitoring_service import MonitoringService
    
    # Run independent checks concurrently
    import asyncio
    container_metrics, db_metrics, redis_metrics, minio_metrics, rmq_metrics, ai_metrics, n8n_metrics = await asyncio.gather(
        MonitoringService.get_container_metrics(),
        MonitoringService.get_database_metrics(db),
        MonitoringService.get_redis_metrics(),
        MonitoringService.get_minio_metrics(),
        MonitoringService.get_rabbitmq_metrics(),
        MonitoringService.get_ai_metrics(),
        MonitoringService.get_n8n_metrics()
    )

    return {
        "timestamp": time.time(),
        "containers": container_metrics,
        "services": {
            "database": db_metrics,
            "redis": redis_metrics,
            "rabbitmq": rmq_metrics,
            "storage": minio_metrics,
            "n8n": n8n_metrics,
            "ai_services": ai_metrics
        }
    }


@router.get("/monitoring/prometheus")
async def get_prometheus_metrics(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Prometheus-Metriken für Dashboard abrufen. (ISO 27001 A.12.4 Audit-Logging)"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090/api/v1/query?query=up")
            result = resp.json()
            await AuditService.log_action(
                db=db,
                client_id=str(current_user.client_id),
                user_id=current_user.id,
                action="monitoring.prometheus.access",
                table_name="monitoring",
                record_id="prometheus",
                new_values={"status": result.get("status"), "query": "up"},
                ip_address="internal",
                user_agent="technik-dashboard",
            )
            return result
    except Exception as e:
        await AuditService.log_action(
            db=db,
            client_id=str(current_user.client_id),
            user_id=current_user.id,
            action="monitoring.prometheus.error",
            table_name="monitoring",
            record_id="prometheus",
            new_values={"error": str(e)},
            ip_address="internal",
            user_agent="technik-dashboard",
        )
        return {"status": "error", "detail": str(e)}


@router.get("/monitoring/alerts")
async def get_alertmanager_alerts(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """AlertManager-Alerts für Dashboard abrufen. (ISO 27001 A.12.4 Audit-Logging)"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://kube-prometheus-stack-alertmanager.monitoring.svc.cluster.local:9093/api/v2/alerts")
            result = resp.json()
            alert_count = len(result) if isinstance(result, list) else 0
            await AuditService.log_action(
                db=db,
                client_id=str(current_user.client_id),
                user_id=current_user.id,
                action="monitoring.alerts.access",
                table_name="monitoring",
                record_id="alerts",
                new_values={"alert_count": alert_count},
                ip_address="internal",
                user_agent="technik-dashboard",
            )
            return result
    except Exception as e:
        await AuditService.log_action(
            db=db,
            client_id=str(current_user.client_id),
            user_id=current_user.id,
            action="monitoring.alerts.error",
            table_name="monitoring",
            record_id="alerts",
            new_values={"error": str(e)},
            ip_address="internal",
            user_agent="technik-dashboard",
        )
        return {"status": "error", "detail": str(e)}


@router.get("/monitoring/loki")
async def get_loki_logs(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Loki-Logs für Dashboard abrufen. (ISO 27001 A.12.4 Audit-Logging)"""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://loki-gateway.monitoring.svc.cluster.local/loki/api/v1/labels")
            result = resp.json()
            await AuditService.log_action(
                db=db,
                client_id=str(current_user.client_id),
                user_id=current_user.id,
                action="monitoring.loki.access",
                table_name="monitoring",
                record_id="loki",
                new_values={"status": result.get("status")},
                ip_address="internal",
                user_agent="technik-dashboard",
            )
            return result
    except Exception as e:
        await AuditService.log_action(
            db=db,
            client_id=str(current_user.client_id),
            user_id=current_user.id,
            action="monitoring.loki.error",
            table_name="monitoring",
            record_id="loki",
            new_values={"error": str(e)},
            ip_address="internal",
            user_agent="technik-dashboard",
        )
        return {"status": "error", "detail": str(e)}


@router.get("/monitoring/cluster-overview")
async def get_cluster_overview(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Aggregierte Cluster-Metriken: Nodes, Pods, CPU, Memory, Disk."""
    import httpx
    prom_url = "http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090/api/v1/query"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            queries = {
                "nodes_ready": 'kube_node_status_condition{condition="Ready",status="true"}',
                "nodes_total": 'kube_node_status_condition{condition="Ready"}',
                "pods_running": 'kube_pod_status_phase{phase="Running"}',
                "pods_failed": 'kube_pod_status_phase{phase="Failed"}',
                "pods_crashloop": 'kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"}',
                "cpu_usage": '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
                "memory_usage": '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100',
                "disk_usage": '(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100',
            }
            results = {}
            for key, query in queries.items():
                try:
                    resp = await client.get(f"{prom_url}?query={query}")
                    data = resp.json()
                    if data.get("status") == "success" and data.get("data", {}).get("result"):
                        values = [float(r["value"][1]) for r in data["data"]["result"]]
                        results[key] = {
                            "value": round(sum(values), 1) if len(values) > 1 else round(values[0], 1),
                            "count": len(values),
                        }
                    else:
                        results[key] = {"value": 0, "count": 0}
                except Exception:
                    results[key] = {"value": 0, "count": 0}

            nodes_ready = int(results.get("nodes_ready", {}).get("value", 0))
            nodes_total = int(results.get("nodes_total", {}).get("count", 0))
            pods_running = int(results.get("pods_running", {}).get("value", 0))
            pods_failed = int(results.get("pods_failed", {}).get("value", 0))
            pods_crash = int(results.get("pods_crashloop", {}).get("value", 0))

            return {
                "nodes": {"ready": nodes_ready, "total": nodes_total},
                "pods": {"running": pods_running, "failed": pods_failed, "crashloop": pods_crash, "healthy": pods_running},
                "cpu_percent": results.get("cpu_usage", {}).get("value", 0),
                "memory_percent": results.get("memory_usage", {}).get("value", 0),
                "disk_percent": results.get("disk_usage", {}).get("value", 0),
            }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/monitoring/alerts-summary")
async def get_alerts_summary(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Aggregierte Alert-Übersicht mit Severity-Counts."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://kube-prometheus-stack-alertmanager.monitoring.svc.cluster.local:9093/api/v2/alerts")
            alerts = resp.json()
            if not isinstance(alerts, list):
                return {"total": 0, "critical": 0, "warning": 0, "info": 0, "alerts": []}
            critical = sum(1 for a in alerts if a.get("labels", {}).get("severity") == "critical")
            warning = sum(1 for a in alerts if a.get("labels", {}).get("severity") == "warning")
            info = sum(1 for a in alerts if a.get("labels", {}).get("severity") not in ("critical", "warning"))
            recent = []
            for a in alerts[:10]:
                recent.append({
                    "name": a.get("labels", {}).get("alertname", "Unknown"),
                    "severity": a.get("labels", {}).get("severity", "unknown"),
                    "summary": a.get("annotations", {}).get("summary", ""),
                    "instance": a.get("labels", {}).get("instance", ""),
                    "state": a.get("status", {}).get("state", ""),
                })
            return {"total": len(alerts), "critical": critical, "warning": warning, "info": info, "alerts": recent}
    except Exception as e:
        return {"total": 0, "critical": 0, "warning": 0, "info": 0, "alerts": [], "error": str(e)}


@router.get("/monitoring/recent-logs")
async def get_recent_logs(
    limit: int = 30,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Letzte Logs aus Loki für das Meeting-Automation Namespace."""
    import httpx, time
    end = int(time.time() * 1e9)
    start = end - (5 * 60 * int(1e9))
    query = '{service_name=~".+"}'
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "http://loki-gateway.monitoring.svc.cluster.local/loki/api/v1/query_range",
                params={"query": query, "start": str(start), "end": str(end), "limit": str(min(limit, 100)), "direction": "backward"},
            )
            data = resp.json()
            logs = []
            if data.get("status") == "success":
                for stream in data.get("data", {}).get("result", []):
                    labels = stream.get("stream", {})
                    pod = labels.get("pod", labels.get("service_name", "unknown"))
                    for ts, line in stream.get("values", []):
                        level = "info"
                        line_lower = line.lower()
                        if "error" in line_lower or "exception" in line_lower or "traceback" in line_lower:
                            level = "error"
                        elif "warning" in line_lower or "warn" in line_lower:
                            level = "warning"
                        logs.append({
                            "timestamp": ts,
                            "pod": pod,
                            "level": level,
                            "message": line[:300],
                        })
            logs.sort(key=lambda x: x["timestamp"], reverse=True)
            return {"logs": logs[:limit], "total": len(logs)}
    except Exception as e:
        return {"logs": [], "total": 0, "error": str(e)}


@router.get("/storage/usage")
async def get_storage_usage_per_tenant(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Storage-Verbrauch aller Tenants für Dashboard. (ISO 27001 A.8.26 Multi-Tenant)"""
    from app.services.storage_quota import get_storage_usage_bytes, get_storage_quota
    from app.models.client import Client as ClientModel
    
    result = await db.execute(select(ClientModel))
    clients = result.scalars().all()
    
    storage_data = []
    for client in clients:
        usage_bytes = get_storage_usage_bytes(str(client.id))
        quota_bytes = get_storage_quota(client.subscription_plan)
        usage_percent = round((usage_bytes / quota_bytes * 100), 2) if quota_bytes > 0 else 0
        
        alerts = []
        if usage_percent >= 90:
            alerts.append({"severity": "critical", "message": f"Storage quota 90% erreicht ({usage_percent}%)"})
        elif usage_percent >= 70:
            alerts.append({"severity": "warning", "message": f"Storage quota 70% erreicht ({usage_percent}%)"})
        elif usage_percent >= 50:
            alerts.append({"severity": "info", "message": f"Storage quota 50% erreicht ({usage_percent}%)"})
        
        storage_data.append({
            "client_id": str(client.id),
            "company_name": client.company_name,
            "subscription_plan": client.subscription_plan.value if client.subscription_plan else "GRATUIT",
            "usage_bytes": usage_bytes,
            "quota_bytes": quota_bytes,
            "usage_percent": usage_percent,
            "alerts": alerts,
        })
    
    await AuditService.log_action(
        db=db,
        client_id=str(current_user.client_id),
        user_id=current_user.id,
        action="monitoring.storage.access",
        table_name="monitoring",
        record_id="storage",
        new_values={"tenant_count": len(storage_data)},
        ip_address="internal",
        user_agent="technik-dashboard",
    )
    
    return {"tenants": storage_data}


# ============================================================
# MANAGEMENT ENDPOINTS — Operations Center
# ============================================================


class ScaleRequest(BaseModel):
    replicas: int


class SilenceRequest(BaseModel):
    matchers: List[dict]
    duration: str = "1h"
    comment: str = ""


K8S_API = "https://kubernetes.default.svc:443"
K8S_NAMESPACE = "meeting-automation-staging"


async def _k8s_request(method: str, path: str, body: dict = None):
    """K8s API Request mit ServiceAccount Token."""
    import httpx
    try:
        token_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        with open(token_path) as f:
            token = f.read().strip()
    except FileNotFoundError:
        return None

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{K8S_API}{path}"
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "DELETE":
                resp = await client.delete(url, headers=headers)
            elif method == "PATCH":
                resp = await client.patch(url, headers=headers, json=body)
            else:
                return None
            return resp.json() if resp.status_code < 400 else {"error": resp.text}
    except Exception as e:
        return {"error": str(e)}


@router.get("/management/pods")
async def list_pods(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Alle Pods mit Status, Restarts, Node, Memory."""
    result = await _k8s_request("GET", f"/api/v1/namespaces/{K8S_NAMESPACE}/pods")
    if not result or "items" not in result:
        return {"pods": [], "error": result.get("error", "K8s API nicht erreichbar")}

    pods = []
    for pod in result["items"]:
        status_info = pod.get("status", {})
        spec = pod.get("spec", {})
        cont_status = status_info.get("containerStatuses", [{}])[0] if status_info.get("containerStatuses") else {}
        restarts = cont_status.get("restartCount", 0)
        phase = status_info.get("phase", "Unknown")
        reason = status_info.get("reason", "")
        node = spec.get("nodeName", "unknown")
        age = ""
        if status_info.get("startTime"):
            from datetime import datetime
            start = datetime.fromisoformat(status_info["startTime"].replace("Z", "+00:00"))
            delta = datetime.now().astimezone() - start
            days = delta.days
            hours = delta.seconds // 3600
            age = f"{days}d {hours}h" if days > 0 else f"{hours}h"

        mem_usage = ""
        cpu_usage = ""
        for cs in status_info.get("containerStatuses", []):
            if "resources" in cs.get("resources", {}):
                mem_limit = spec.get("containers", [{}])[0].get("resources", {}).get("limits", {}).get("memory", "")
                cpu_limit = spec.get("containers", [{}])[0].get("resources", {}).get("limits", {}).get("cpu", "")
                mem_usage = mem_limit
                cpu_usage = cpu_limit

        pods.append({
            "name": pod["metadata"]["name"],
            "status": phase,
            "reason": reason or cont_status.get("reason", ""),
            "restarts": restarts,
            "node": node,
            "age": age,
            "memory_limit": mem_usage,
            "cpu_limit": cpu_usage,
            "ready": cont_status.get("ready", False),
            "image": spec.get("containers", [{}])[0].get("image", "unknown") if spec.get("containers") else "unknown",
        })

    await AuditService.log_action(
        db=db, client_id=str(current_user.client_id), user_id=current_user.id,
        action="management.pods.list", table_name="management", record_id="pods",
        new_values={"pod_count": len(pods)}, ip_address="internal", user_agent="technik-dashboard",
    )
    return {"pods": pods}


@router.get("/management/pods/{pod_name}/logs")
async def get_pod_logs(
    pod_name: str,
    lines: int = 100,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Pod-Logs abrufen."""
    result = await _k8s_request("GET", f"/api/v1/namespaces/{K8S_NAMESPACE}/pods/{pod_name}/log?tailLines={lines}")
    if not result or "error" in result:
        return {"logs": [], "error": result.get("error", "Logs nicht verfügbar")}

    log_lines = result.split("\n") if isinstance(result, str) else []
    logs = []
    for line in log_lines:
        if not line.strip():
            continue
        level = "info"
        ll = line.lower()
        if "error" in ll or "exception" in ll or "traceback" in ll:
            level = "error"
        elif "warning" in ll or "warn" in ll:
            level = "warning"
        logs.append({"line": line[:500], "level": level})

    await AuditService.log_action(
        db=db, client_id=str(current_user.client_id), user_id=current_user.id,
        action="management.pods.logs", table_name="management", record_id=pod_name,
        new_values={"line_count": len(logs)}, ip_address="internal", user_agent="technik-dashboard",
    )
    return {"logs": logs, "total": len(logs)}


@router.post("/management/pods/{pod_name}/restart")
async def restart_pod(
    pod_name: str,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Pod neu starten (delete → k8s recreated)."""
    result = await _k8s_request("DELETE", f"/api/v1/namespaces/{K8S_NAMESPACE}/pods/{pod_name}")
    await AuditService.log_action(
        db=db, client_id=str(current_user.client_id), user_id=current_user.id,
        action="management.pods.restart", table_name="management", record_id=pod_name,
        new_values={"result": "ok" if not result or "error" not in result else result.get("error")},
        ip_address="internal", user_agent="technik-dashboard",
    )
    return {"status": "restarted", "pod": pod_name}


@router.get("/management/storage/buckets")
async def list_buckets(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """MinIO Buckets mit Size und Object-Count."""
    import boto3, httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("http://minio-staging:9000/minio/health/live")
    except Exception:
        pass

    s3 = boto3.client("s3",
        endpoint_url="http://minio-staging:9000",
        aws_access_key_id="minio_user",
        aws_secret_access_key="minio_password",
        region_name="us-east-1",
    )
    buckets = []
    try:
        for bucket in s3.list_buckets()["Buckets"]:
            name = bucket["Name"]
            objects = list(s3.list_objects_v2(Bucket=name).get("Contents", []))
            size = sum(o.get("Size", 0) for o in objects)
            buckets.append({"name": name, "objects": len(objects), "size_bytes": size,
                           "size_human": f"{size / (1024*1024):.2f} MB",
                           "created": bucket["CreationDate"].isoformat()})
    except Exception as e:
        return {"buckets": [], "error": str(e)}

    await AuditService.log_action(
        db=db, client_id=str(current_user.client_id), user_id=current_user.id,
        action="management.storage.buckets", table_name="management", record_id="storage",
        new_values={"bucket_count": len(buckets)}, ip_address="internal", user_agent="technik-dashboard",
    )
    return {"buckets": buckets}


@router.get("/management/storage/buckets/{bucket_name}/objects")
async def list_bucket_objects(
    bucket_name: str,
    prefix: str = "",
    limit: int = 100,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Objekte in einem Bucket auflisten."""
    import boto3
    s3 = boto3.client("s3",
        endpoint_url="http://minio-staging:9000",
        aws_access_key_id="minio_user",
        aws_secret_access_key="minio_password",
        region_name="us-east-1",
    )
    try:
        resp = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix, MaxKeys=limit)
        objects = []
        for obj in resp.get("Contents", []):
            objects.append({
                "key": obj["Key"], "size_bytes": obj["Size"],
                "size_human": f"{obj['Size'] / (1024*1024):.2f} MB",
                "last_modified": obj["LastModified"].isoformat(),
            })
        return {"objects": objects, "truncated": resp.get("IsTruncated", False),
                "total": resp.get("KeyCount", 0)}
    except Exception as e:
        return {"objects": [], "error": str(e)}


@router.get("/management/redis/info")
async def redis_info(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Redis Info: version, memory, keys, hitrate."""
    import redis as redis_lib
    try:
        r = redis_lib.Redis(host="redis-staging", port=6379, password="redis_password", decode_responses=True)
        info = r.info()
        dbsize = r.dbsize()
        return {
            "version": info.get("redis_version", "?"),
            "memory_used": info.get("used_memory_human", "?"),
            "memory_peak": info.get("used_memory_peak_human", "?"),
            "memory_max": info.get("maxmemory_human", "0"),
            "total_keys": dbsize,
            "connected_clients": info.get("connected_clients", 0),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
            "hit_rate": round(info.get("keyspace_hits", 0) / max(info.get("keyspace_hits", 0) + info.get("keyspace_misses", 1), 1) * 100, 1),
            "evicted_keys": info.get("evicted_keys", 0),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/management/redis/keys")
async def redis_keys(
    pattern: str = "*",
    limit: int = 50,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Redis Keys mit TTL und Typ."""
    import redis as redis_lib
    try:
        r = redis_lib.Redis(host="redis-staging", port=6379, password="redis_password", decode_responses=True)
        keys = []
        for key in r.scan_iter(match=pattern, count=limit):
            ktype = r.type(key)
            ttl = r.ttl(key)
            size = r.memory_usage(key) or 0
            val_preview = ""
            if ktype == "string":
                val_preview = r.get(key)[:100] if r.get(key) else ""
            elif ktype == "list":
                val_preview = f"{r.llen(key)} items"
            elif ktype == "hash":
                val_preview = f"{r.hlen(key)} fields"
            elif ktype == "set":
                val_preview = f"{r.scard(key)} members"
            keys.append({"key": key, "type": ktype, "ttl": ttl, "memory": size, "preview": val_preview})
            if len(keys) >= limit:
                break
        return {"keys": keys, "total": r.dbsize()}
    except Exception as e:
        return {"keys": [], "error": str(e)}


@router.post("/management/redis/flush")
async def redis_flush(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Alle Redis Keys löschen (mit Bestätigung)."""
    import redis as redis_lib
    try:
        r = redis_lib.Redis(host="redis-staging", port=6379, password="redis_password", decode_responses=True)
        count = r.dbsize()
        r.flushdb()
        await AuditService.log_action(
            db=db, client_id=str(current_user.client_id), user_id=current_user.id,
            action="management.redis.flush", table_name="management", record_id="redis",
            new_values={"keys_deleted": count}, ip_address="internal", user_agent="technik-dashboard",
        )
        return {"status": "flushed", "keys_deleted": count}
    except Exception as e:
        return {"error": str(e)}


@router.get("/management/deployments")
async def list_deployments(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Alle Deployments mit Replica-Status."""
    result = await _k8s_request("GET", f"/apis/apps/v1/namespaces/{K8S_NAMESPACE}/deployments")
    if not result or "items" not in result:
        return {"deployments": [], "error": result.get("error", "K8s API nicht erreichbar")}

    deployments = []
    for dep in result["items"]:
        status_info = dep.get("status", {})
        spec = dep.get("spec", {})
        deployments.append({
            "name": dep["metadata"]["name"],
            "desired": spec.get("replicas", 0),
            "ready": status_info.get("readyReplicas", 0),
            "available": status_info.get("availableReplicas", 0),
            "updated": status_info.get("updatedReplicas", 0),
            "image": spec.get("template", {}).get("spec", {}).get("containers", [{}])[0].get("image", "?"),
        })
    return {"deployments": deployments}


@router.patch("/management/deployments/{dep_name}/scale")
async def scale_deployment(
    dep_name: str,
    body: ScaleRequest,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Deployment Replica-Anzahl ändern."""
    result = await _k8s_request("PATCH",
        f"/apis/apps/v1/namespaces/{K8S_NAMESPACE}/deployments/{dep_name}/scale",
        {"spec": {"replicas": body.replicas}})
    await AuditService.log_action(
        db=db, client_id=str(current_user.client_id), user_id=current_user.id,
        action="management.deployments.scale", table_name="management", record_id=dep_name,
        new_values={"replicas": body.replicas}, ip_address="internal", user_agent="technik-dashboard",
    )
    return {"status": "scaled", "deployment": dep_name, "replicas": body.replicas}


@router.post("/management/alerts/silence")
async def silence_alert(
    body: SilenceRequest,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Alert vorübergehend stummschalten."""
    import httpx
    try:
        silence = {
            "matchers": body.matchers,
            "startsAt": datetime.utcnow().isoformat() + "Z",
            "endsAt": (datetime.utcnow() + _parse_duration(body.duration)).isoformat() + "Z",
            "createdBy": current_user.email,
            "comment": body.comment or f"Silenced by {current_user.email}",
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post("http://kube-prometheus-stack-alertmanager.monitoring.svc.cluster.local:9093/api/v2/silences", json=silence)
            result = resp.json() if resp.status_code < 400 else {"error": resp.text}
        await AuditService.log_action(
            db=db, client_id=str(current_user.client_id), user_id=current_user.id,
            action="management.alerts.silence", table_name="management", record_id="silence",
            new_values={"matchers": body.matchers, "duration": body.duration}, ip_address="internal", user_agent="technik-dashboard",
        )
        return result
    except Exception as e:
        return {"error": str(e)}


def _parse_duration(d: str) -> timedelta:
    unit = d[-1]
    value = int(d[:-1])
    if unit == "m": return timedelta(minutes=value)
    if unit == "h": return timedelta(hours=value)
    if unit == "d": return timedelta(days=value)
    return timedelta(hours=1)


@router.get("/management/alerts/silences")
async def list_silences(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Aktive Alert-Silences."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://kube-prometheus-stack-alertmanager.monitoring.svc.cluster.local:9093/api/v2/silences")
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


@router.delete("/management/alerts/silence/{silence_id}")
async def delete_silence(
    silence_id: str,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Alert-Silence entfernen."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.delete(f"http://kube-prometheus-stack-alertmanager.monitoring.svc.cluster.local:9093/api/v2/silence/{silence_id}")
        await AuditService.log_action(
            db=db, client_id=str(current_user.client_id), user_id=current_user.id,
            action="management.alerts.unsilence", table_name="management", record_id=silence_id,
            new_values={"action": "delete"}, ip_address="internal", user_agent="technik-dashboard",
        )
        return {"status": "deleted", "silence_id": silence_id}
    except Exception as e:
        return {"error": str(e)}


@router.post("/management/reload/prometheus")
async def reload_prometheus(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Prometheus Config neu laden."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post("http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090/-/reload")
        await AuditService.log_action(
            db=db, client_id=str(current_user.client_id), user_id=current_user.id,
            action="management.reload.prometheus", table_name="management", record_id="prometheus",
            new_values={"status": resp.status_code}, ip_address="internal", user_agent="technik-dashboard",
        )
        return {"status": "reloaded", "service": "prometheus"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/management/backups")
async def list_backups(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """PostgreSQL Backups aus Longhorn PVC."""
    result = await _k8s_request("GET", f"/apis/batch/v1/namespaces/{K8S_NAMESPACE}/jobs?labelSelector=job-name")
    pods = result.get("items", []) if result else []
    backups = []
    for pod in pods:
        name = pod["metadata"]["name"]
        status = pod.get("status", {}).get("phase", "?")
        created = pod.get("metadata", {}).get("creationTimestamp", "")
        backups.append({"name": name, "status": status, "created": created})
    backups.sort(key=lambda x: x["created"], reverse=True)
    return {"backups": backups[:20]}


@router.get("/management/networkpolicies")
async def list_network_policies(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """Alle NetworkPolicies mit Details."""
    result = await _k8s_request("GET", f"/apis/networking.k8s.io/v1/namespaces/{K8S_NAMESPACE}/networkpolicies")
    if not result or "items" not in result:
        return {"policies": []}

    policies = []
    for np in result["items"]:
        spec = np.get("spec", {})
        pod_selector = spec.get("podSelector", {}).get("matchLabels", {})
        ingress_rules = []
        for rule in spec.get("ingress", []):
            for fr in rule.get("from", []):
                if "podSelector" in fr:
                    ingress_rules.append(f"pod: {fr['podSelector'].get('matchLabels', {})}")
                elif "namespaceSelector" in fr:
                    ingress_rules.append(f"ns: {fr['namespaceSelector'].get('matchLabels', {})}")
                elif "ipBlock" in fr:
                    ingress_rules.append(f"ip: {fr['ipBlock'].get('cidr', '?')}")
        policies.append({
            "name": np["metadata"]["name"],
            "pod_selector": pod_selector,
            "ingress_rules": ingress_rules,
            "ingress_count": len(ingress_rules),
        })
    return {"policies": policies, "total": len(policies)}


# ============================================================
# ARGOCD ENDPOINTS
# ============================================================

ARGOCD_URL = "https://staging.meeting-automation.com/argocd"
ARGOCD_USER = "admin"
ARGOCD_PASS = "sHy9ErW4UjfQHkMs"


async def _argocd_token() -> str:
    """ArgoCD Session-Token holen."""
    import httpx
    async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
        resp = await client.post(f"{ARGOCD_URL}/api/v1/session",
            json={"username": ARGOCD_USER, "password": ARGOCD_PASS})
        return resp.json().get("token", "")


async def _argocd_api(path: str, method: str = "GET", body: dict = None):
    """ArgoCD API Request."""
    import httpx
    token = await _argocd_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        url = f"{ARGOCD_URL}{path}"
        if method == "GET":
            resp = await client.get(url, headers=headers)
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=body or {})
        else:
            resp = await client.delete(url, headers=headers)
        return resp.json() if resp.status_code < 400 else {"error": resp.text}


@router.get("/argocd/applications")
async def argocd_list_apps(
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """ArgoCD Applications auflisten."""
    result = await _argocd_api("/api/v1/applications")
    apps = []
    for app in result.get("items", []):
        status = app.get("status", {})
        apps.append({
            "name": app["metadata"]["name"],
            "namespace": app["metadata"].get("namespace", "argocd"),
            "sync_status": status.get("sync", {}).get("status", "Unknown"),
            "health_status": status.get("health", {}).get("status", "Unknown"),
            "last_sync": status.get("operationState", {}).get("finishedAt", ""),
            "revision": status.get("sync", {}).get("revision", "")[:12],
            "source_path": app.get("spec", {}).get("source", {}).get("path", ""),
        })
    await AuditService.log_action(
        db=db, client_id=str(current_user.client_id), user_id=current_user.id,
        action="argocd.applications.list", table_name="argocd", record_id="apps",
        new_values={"app_count": len(apps)}, ip_address="internal", user_agent="technik-dashboard",
    )
    return {"applications": apps, "total": len(apps)}


@router.get("/argocd/applications/{app_name}")
async def argocd_get_app(
    app_name: str,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """ArgoCD Application Details."""
    return await _argocd_api(f"/api/v1/applications/{app_name}")


@router.post("/argocd/applications/{app_name}/sync")
async def argocd_sync_app(
    app_name: str,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """ArgoCD Application sync auslösen."""
    result = await _argocd_api(f"/api/v1/applications/{app_name}/sync", method="POST")
    await AuditService.log_action(
        db=db, client_id=str(current_user.client_id), user_id=current_user.id,
        action="argocd.applications.sync", table_name="argocd", record_id=app_name,
        new_values={"action": "sync"}, ip_address="internal", user_agent="technik-dashboard",
    )
    return result


@router.get("/argocd/applications/{app_name}/diff")
async def argocd_diff_app(
    app_name: str,
    current_user: UserModel = Depends(deps.get_current_system_admin),
    db: AsyncSession = Depends(deps.get_db),
):
    """ArgoCD Application Diff (gewünscht vs aktuell)."""
    return await _argocd_api(f"/api/v1/applications/{app_name}/diff?respectspect=true")

