# E2E_TEST Rollback Protocol — 2026-08-12

## Problem
Staging Backend hatte `E2E_TEST=true` gesetzt (seit 2026-08-04, Commit `1c43730f`).
Dadurch liefen ALLE Celery Tasks synchron im Backend (`task_always_eager=True`),
statt auf den Celery Workers. Recording test1520 blieb in Status "transcribing" hängen.

Production hatte `E2E_TEST` NICHT gesetzt → Pipeline funktionierte dort.

## Root Cause
```python
# celery_app.py Zeile 26-28
if os.getenv("E2E_TEST", "").lower() == "true":
    celery_app.conf.task_always_eager = True  # Tasks laufen synchron im Backend
    celery_app.conf.task_eager_propagates = True
```

## Fix
`E2E_TEST=true` aus dem Staging Backend Deployment entfernt.

## Vorher-Zustand (BEFORE)
```yaml
# Backend Container:
- name: E2E_TEST
  value: "true"    # ← DAS WURDE ENTFERNT

# Init Container (alembic-migrate):
- name: E2E_TEST
  value: "false"   # ← UNVERÄNDERT (soll so sein)
```

- Deployment YAML: `/tmp/backend-deployment-BEFORE.yaml`
- Git Commit (hinzugefügt): `1c43730f` am 2026-08-04
- Recording test1520: Status `transcribing`, 4.27 MB

## Nachher-Zustand (AFTER)
```yaml
# Backend Container:
- name: E2E_TEST
  value: "false"   # ← GEÄNDERT

# Init Container (alembic-migrate):
- name: E2E_TEST
  value: "false"   # ← UNVERÄNDERT
```

## ROLLBACK-Befehle (falls nötig)

### Option 1: Schnell-Rollback (E2E_TEST wieder aktivieren)
```bash
kubectl set env deployment/backend E2E_TEST=true -n meeting-automation-staging
kubectl rollout status deployment/backend -n meeting-automation-staging --timeout=120s
```

### Option 2: Aus gesichertem YAML
```bash
kubectl apply -f /tmp/backend-deployment-BEFORE.yaml -n meeting-automation-staging
kubectl rollout status deployment/backend -n meeting-automation-staging --timeout=120s
```

### Option 3: Über Git (wenn gepusht)
```bash
cd /home/opc/meeting-automation
git revert HEAD  # oder manuell
kubectl apply -f infrastructure/kubernetes/staging/backend-deployment.yaml
```

## Verifikation nach Rollback
```bash
# Prüfe ob E2E_TEST wieder true ist
kubectl get deployment backend -n meeting-automation-staging -o yaml | grep E2E_TEST

# Prüfe ob Celery Workers Tasks empfangen
kubectl logs -n meeting-automation-staging -l app=celery-worker-pro --tail=20 | grep process_recording
```

## Wann Rollback nötig?
- Wenn E2E Tests auf Staging nicht mehr funktionieren (task_always_eager nötig)
- Wenn Celery Workers Tasks nicht verarbeiten können
- Wenn die Pipeline IMMER noch hängt (dann ist E2E_TEST NICHT die Ursache)

## Datum der Änderung
2026-08-12 ~17:05 UTC

## Durchgeführt von
Buffy (AI Agent)
