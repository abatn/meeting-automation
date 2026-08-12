# Sentinel Rollback-Plan — 2026-08-12

## Was geändert wurde

| Datei | Änderung |
|-------|----------|
| `.github/workflows/ci.yml:173` | `SKIP_SENTINEL=true` → `SKIP_SENTINEL=false` |

## Warum

- CI baut seit Einführung mit `SKIP_SENTINEL=true`
- Dockerfile überspringt dadurch `pip install llama-cpp-python` + Modell-Download
- Sentinel LLM läuft im Fallback-Modus (keine echte LLM-Summarization)
- `.loop.md` Phase 163, Lesson C7: "SKIP_SENTINEL=true darf NIEMALS für Prod/Staging genutzt werden"

## Auswirkung

| Vorher | Nachher |
|--------|---------|
| Build ~3 Min | Build ~7-8 Min (Cache) |
| Kein llama-cpp-python | llama-cpp-python 0.3.34 installiert |
| Kein Qwen-Modell im Image | Qwen-1.5B GGUF (1.1GB) im Image |
| Sentinel: Fallback | Sentinel: LLM-Modus |

## Rollback (falls nötig)

```bash
# CI zurücksetzen
cd /home/opc/meeting-automation
sed -i 's/SKIP_SENTINEL=false/SKIP_SENTINEL=true/' .github/workflows/ci.yml
git add .github/workflows/ci.yml
git commit -m "revert(ci): SKIP_SENTINEL=true (Sentinel Rollback)"
git push
```

**Wann rollbacken?**
- Wenn Build-Timeout (>10 Min) auftritt
- Wenn Docker-Hub Speicherplatz-Limit erreicht
- Wenn PRO Worker OOM bei Modell-Download

## Verifikation nach Deploy

```bash
# 1. PRO Worker prüfen
kubectl exec -n meeting-automation-staging celery-worker-pro-staging-<pod> -c celery-worker -- python3 -c "
from app.services.sentinel_service import get_sentinel_service
svc = get_sentinel_service()
print('type:', type(svc).__name__)
print('is_available:', svc.is_available)
"

# Erwartet: is_available = True (nicht Fallback)
```

## CI-Build Prüfen

Nach Push: GitHub Actions → ci.yml → Build-Log prüfen:
- Zeile: `pip install llama-cpp-python>=0.3.0` (sollte NICHT übersprungen werden)
- Zeile: `qwen2.5-1.5b-instruct-q4_k_m.gguf` (sollte heruntergeladen werden)
