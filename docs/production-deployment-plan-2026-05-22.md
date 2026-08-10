# Production Deployment Analyse & Plan

**Datum**: 2026-05-22
**Status**: pending-review
**Tags**: production, kubernetes, deployment, alembic, iso27001

---

## Ausgangslage

- **E2E-Tests**: 168 passed, 0 failed, 2 skipped
- **Infrastruktur**: 19 K8s Manifests (prod) + 17 (staging)
- **CI/CD**: 3-stufige Pipeline (dev → staging → prod mit manueller Freigabe)
- **entrypoint.sh**: Implementiert, nutzt E2E, aber nicht in K8s konfiguriert
- **Migrations**: Aktuell manuell nach Deploy → ISO 27001 Risiko

---

## KRITISCH (P0 – diese Woche)

### 1. Kein initContainer für Alembic-Migrationen
- **Betroffen**: `infrastructure/kubernetes/backend-deployment.yaml`, `infrastructure/kubernetes/staging/backend-deployment.yaml`
- **Problem**: Weder Production noch Staging haben einen initContainer. `alembic upgrade head` wird nie automatisch ausgeführt.
- **Risiko**: Schema-Drift, App-Crash bei neuen Spalten, ISO 27001 Compliance-Lücke
- **Lösung**: initContainer vor dem Backend-Container einfügen

### 2. DB_HOST env var fehlt/falsch in Staging
- **Betroffen**: `infrastructure/kubernetes/staging/backend-deployment.yaml`
- **Problem**: entrypoint.sh default ist `DB_HOST=postgres`, aber Staging-Service heißt `postgres-staging`
- **Risiko**: entrypoint.sh kann keine DB-Verbindung aufbauen
- **Lösung**: `DB_HOST: postgres-staging` explizit setzen

### 3. SOPS-Secrets werden in CI nicht entschlüsselt
- **Betroffen**: `.github/workflows/e2e-tests.yml (DEPRECATED):314`
- **Problem**: `kubectl apply` wendet verschlüsselte Secrets als Plaintext an
- **Risiko**: Production-Secrets sind unbrauchbar
- **Lösung**: SOPS age key als GitHub Secret, vor kubectl apply entschlüsseln

### 4. DEBUG=true in Production
- **Betroffen**: `infrastructure/kubernetes/backend-config.yaml:7`
- **Lösung**: Auf `false` ändern

### 5. CORS nur localhost
- **Betroffen**: `infrastructure/kubernetes/backend-config.yaml:22`
- **Lösung**: Production-Domain hinzufügen

### 6. Traefik Ingress nur localhost
- **Betroffen**: `infrastructure/kubernetes/traefik-ingressroute.yaml`
- **Lösung**: Production-Domain eintragen

### 7. Traefik Admin API ungesichert
- **Betroffen**: `infrastructure/kubernetes/traefik-deployment.yaml:23`
- **Lösung**: `--api.insecure=true` entfernen

---

## WICHTIG (P1 – nächste Woche)

| # | Problem | Datei |
|---|---------|-------|
| 8 | Frontend-Image hardcoded v1.0.0 + imagePullPolicy: Never | frontend-deployment.yaml |
| 9 | Kein Frontend-Deploy-Step in CI | e2e-tests.yml (DEPRECATED) |
| 10 | Keine Health Checks für Celery Worker/Beat | celery-*-deployment.yaml |
| 11 | Keine Resource Limits für StatefulSets | postgres, redis, rabbitmq, minio |
| 12 | Staging-Secrets Plaintext im Repo | staging/*-secrets.yaml |
| 13 | Staging nutzt hostPath statt PVC | postgres, minio statefulsets |
| 14 | TLS-Zertifikat self-signed | traefik-tls-secret.yaml |

---

## NIEDRIG (P2+ – später)

| # | Problem |
|---|---------|
| 15 | Kein DB-Backup-Skript (ISO 27001 Lücke) |
| 16 | Terraform ist leer |
| 17 | Keine Pod Disruption Budgets |
| 18 | Keine Horizontal Pod Autoscalers |
| 19 | Kein Monitoring |
| 20 | Duplicate Docker Builds |

---

## Umsetzungsplan

### Phase 1 (P0)
- [ ] initContainer Production
- [ ] initContainer Staging
- [ ] DB_HOST=postgres-staging in Staging
- [ ] SOPS-Decryption in CI
- [ ] DEBUG=false Production
- [ ] CORS_ORIGINS Production-Domain
- [ ] Traefik Ingress Production-Domain
- [ ] Traefik api.insecure entfernen

### Phase 2 (P1)
- [ ] Frontend-Image-Tag dynamisch
- [ ] Frontend-Deploy-Step in CI
- [ ] Celery Health Checks
- [ ] Resource Limits StatefulSets
- [ ] Staging-Secrets SOPS
- [ ] Staging hostPath → PVC

### Phase 3 (P2+)
- [ ] TLS-Zertifikat ersetzen
- [ ] DB-Backup-Skript
- [ ] Terraform
- [ ] PDBs + HPAs
- [ ] Monitoring

---

## Dependencies

- **SOPS age key**: age1yyrjgyvppvvatk9ngf03mn28wqd0pmx5frq02gmrcms3cz4t5chqwwn0kh
- **GitHub Secrets**: KUBE_CONFIG_PRODUCTION, KUBE_CONFIG_STAGING, SOPS_AGE_KEY, DOCKERHUB_TOKEN
- **Extern**: DNS für meeting-automate.tn, TLS-Zertifikat
