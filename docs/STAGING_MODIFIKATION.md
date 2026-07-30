# Staging Modifikation — Bug Fixes

**Stand:** 2026-07-29
**Status:** Offen
**Betroffen:** Production Deploy + Sentinel Pipeline

---

## Fix 1: Container-Name in `e2e-tests.yml`

**Datei:** `.github/workflows/e2e-tests.yml` (Zeilen 382-387)

**Problem:**
`kubectl set image` nutzt Container-Name `celery=` — aber der tatsächliche Container-Name in beiden Deployments ist `celery-worker`.

**Nachweis:**
- `celery-worker-deployment.yaml` Zeile 22: `name: celery-worker`
- `celery-worker-pro-deployment.yaml` Zeile 22: `name: celery-worker`

**Änderung:**

```yaml
# ALT (Zeile 382-387):
kubectl set image deployment/celery-worker \
  celery=${{ env.IMAGE_NAME }}:${{ github.sha }} \
  -n meeting-automation --record
kubectl set image deployment/celery-worker-pro \
  celery=${{ env.IMAGE_NAME }}:${{ github.sha }} \
  -n meeting-automation --record

# NEU:
kubectl set image deployment/celery-worker \
  celery-worker=${{ env.IMAGE_NAME }}:${{ github.sha }} \
  -n meeting-automation --record
kubectl set image deployment/celery-worker-pro \
  celery-worker=${{ env.IMAGE_NAME }}:${{ github.sha }} \
  -n meeting-automation --record
```

**Warum:** Ohne diesen Fix schlägt jeder `deploy-production` Job in der E2E Pipeline fehl.

---

## Fix 2+3: Plan-Vergleich in `celery_app.py`

**Datei:** `backend/app/tasks/celery_app.py` (Zeilen 78 und 96)

**Problem:**
`plan.value in ("pro", "entrepise")` vergleicht lowercase + Tippfehler gegen uppercase Enum-Werte.

**Nachweis:**
```python
# backend/app/models/client.py
class SubscriptionPlan(str, enum.Enum):
    GRATUIT = "GRATUIT"
    PRO = "PRO"              # ← uppercase
    ENTREPRISE = "ENTREPRISE" # ← uppercase
```

**Änderung Zeile 78:**
```python
# ALT:
if plan and plan.value in ("pro", "entrepise"):

# NEU:
if plan and plan.value in ("PRO", "ENTREPRISE"):
```

**Änderung Zeile 96:**
```python
# ALT:
if plan and plan.value in ("pro", "entrepise"):

# NEU:
if plan and plan.value in ("PRO", "ENTREPRISE"):
```

**Warum:**
Ohne diesen Fix matcht der Vergleich NIE → alle PRO/ENTREPRISE-Recordings landen auf `transcription_gratuit` (FREE-Worker) statt `transcription_pro` (Sentinel-Worker). Sentinel LLM wird nie getriggert.

---

## Zusammenfassung

| # | Datei | Zeile | Alt | Neu | Priorität |
|---|-------|-------|-----|-----|-----------|
| 1 | `.github/workflows/e2e-tests.yml` | 383 | `celery=` | `celery-worker=` | Hoch (Deploy blockiert) |
| 2 | `.github/workflows/e2e-tests.yml` | 386 | `celery=` | `celery-worker=` | Hoch (Deploy blockiert) |
| 3 | `backend/app/tasks/celery_app.py` | 78 | `("pro", "entrepise")` | `("PRO", "ENTREPRISE")` | Hoch (Sentinel blockiert) |
| 4 | `backend/app/tasks/celery_app.py` | 96 | `("pro", "entrepise")` | `("PRO", "ENTREPRISE")` | Hoch (Sentinel blockiert) |

## Ausführung

1. Fixes anwenden
2. Push auf `main`
3. CI Pipeline laufen lassen (Backend CI + Docker Build + E2E)
4. E2E Pipeline `deploy-production` Job sollte jetzt durchlaufen
5. Sentinel-Worker empfängt PRO/ENTREPRISE-Recordings korrekt
