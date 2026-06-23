# Kubernetes Deployment Workarounds & Known Issues

> **Datum**: 2026-06-22 (updated)
> **Umgebung**: Kind Cluster `meeting-staging` (Node: `meeting-staging-control-plane`, IP: `172.18.0.3`)
> **Status**: Alle 14 Pods Running ✅, LiveKit PUBLIC_URL gefixt ✅

---

## Quick Start: Clean Deploy

```bash
# 1. Alten Stack löschen
kubectl delete namespace meeting-automation 2>/dev/null

# 2. Setup-Script ausführen
bash setup-kubernetes.sh
```

> ⚠️ Das Script wird bei **Postgres wait** timeouten (DNS fehlt noch). Die folgenden Workarounds manuell anwenden.

---

## Workaround 1: Local-Path Provisioner installieren

**Problem**: PVCs bleiben im `Pending`-Status. Der `rancher.io/local-path` Provisioner ist im Cluster nicht als Pod vorhanden.

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml
kubectl wait --for=condition=ready pod -l app=local-path-provisioner -n local-path-storage --timeout=30s
```

**Root Cause**: Docker Desktop K8s / kind liefert den Provisioner nicht automatisch mit.

---

## Workaround 2: CoreDNS ConfigMap fixen

**Problem**: CoreDNS crashlooped mit `Unknown directive '}STUBDOMAINS'`. Die ConfigMap enthält nicht ersetzte Template-Variablen (`CLUSTER_DOMAIN`, `UPSTREAMNAMESERVER`, `STUBDOMAINS`).

```bash
kubectl create configmap coredns -n kube-system --from-literal=Corefile='.:53 {
    errors
    health {
      lameduck 5s
    }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
      fallthrough in-addr.arpa ip6.arpa
    }
    prometheus :9153
    forward . /etc/resolv.conf
    cache 30
    loop
    reload
    loadbalance
}' --dry-run=client -o yaml | kubectl apply -f -

# CoreDNS neustarten
kubectl delete pod -n kube-system -l k8s-app=kube-dns
kubectl wait --for=condition=ready pod -n kube-system -l k8s-app=kube-dns --timeout=30s
```

**DNS-Test**:
```bash
kubectl run dns-test --rm -it --image=busybox:1.28 --restart=Never -- nslookup postgres.meeting-automation.svc.cluster.local
```

---

## Workaround 3: Redis Secret Key-Name

**Problem**: Redis Deployment erwartet Secret-Key `password`, aber `redis-secrets.yaml` enthält `REDIS_PASSWORD`.

**Fix**: `infrastructure/kubernetes/redis-secrets.yaml`:
```yaml
stringData:
  password: redis_password_prod  # NICHT REDIS_PASSWORD
```

Danach neu verschlüsseln und anwenden:
```bash
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
sops -e -i infrastructure/kubernetes/redis-secrets.yaml
sops -d infrastructure/kubernetes/redis-secrets.yaml | kubectl apply -f -
```

---

## Workaround 4: Backend PYTHONPATH

**Problem**: Alembic und entrypoint.sh finden das `app`-Modul nicht → `ModuleNotFoundError: No module named 'app'`.

**Fix 1 – entrypoint.sh** (`backend/entrypoint.sh` Zeile 47-49):
```bash
echo "=== Running Alembic Migrations (ISO 27001 compliant) ==="
export PYTHONPATH=/app
cd /app
alembic upgrade head
```

**Fix 2 – initContainer command** (`infrastructure/kubernetes/backend-deployment.yaml`):
```yaml
initContainers:
- name: alembic-migrate
  command: ["/bin/sh", "-c", "export PYTHONPATH=/app && cd /app && alembic upgrade head"]
```

**Fix 3 – Backend Container env** (gleiche Datei):
```yaml
containers:
- name: backend
  env:
  - name: PYTHONPATH
    value: "/app"
```

---

## Workaround 5: CELERY_BROKER_URL

**Problem**: Celery Worker crashlooped mit `ACCESS_REFUSED - Login was refused`. Der Default-Wert in `config.py` (`amqp://rabbit_user:rabbit_password@rabbitmq:5672//`) hat das falsche Passwort.

**Fix**: `CELERY_BROKER_URL` zu `backend-secrets.yaml` hinzufügen:
```yaml
stringData:
  CELERY_BROKER_URL: amqp://rabbit_user:rabbit_password_prod@rabbitmq:5672//
```

Neu verschlüsseln und anwenden:
```bash
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
sops -e -i infrastructure/kubernetes/backend-secrets.yaml
sops -d infrastructure/kubernetes/backend-secrets.yaml | kubectl apply -f -
kubectl rollout restart deployment/celery-worker -n meeting-automation
```

---

## Workaround 6: n8n DB-User und N8N_PORT

**Problem**: n8n crashlooped mit:
1. `password authentication failed for user "postgres"` – fehlender `DB_POSTGRESDB_USER`
2. `Invalid number value for N8N_PORT: tcp://10.96.98.113:5678` – K8s injectet den Service-Port als ENV-Variable

**Fix** (`infrastructure/kubernetes/n8n-deployment.yaml`):
```yaml
env:
- name: DB_POSTGRESDB_USER
  value: "meeting_user"
- name: N8N_PORT
  value: "5678"
```

---

## Workaround 7: Docker Images in den Cluster laden

**Problem**: `ErrImageNeverPull` – Frontend-Image ist auf dem Docker-Host, aber nicht im containerd des K8s-Nodes.

**Lösung**:
```bash
# Image bauen
docker build -t meeting-automation-frontend:latest -f frontend/Dockerfile frontend/

# Image in containerd des K8s-Nodes importieren
docker save meeting-automation-frontend:latest | docker exec -i desktop-control-plane ctr -n k8s.io images import -

# Deployment neustarten
kubectl rollout restart deployment/frontend -n meeting-automation
kubectl wait --for=condition=ready pod -l app=frontend -n meeting-automation --timeout=120s
```

**Hinweis**: Das Backend-Image muss ebenfalls so geladen werden, wenn es neu gebaut wird:
```bash
docker save meeting-automation-backend:latest | docker exec -i desktop-control-plane ctr -n k8s.io images import -
kubectl rollout restart deployment/backend -n meeting-automation
```

---

## Workaround 8: Terminating PVCs forcieren

**Problem**: PVCs hängen im `Terminating`-Status (Finalizer-Blockade), neue StatefulSets können nicht starten.

```bash
kubectl delete pvc -n meeting-automation <pvc-name> --force
```

**Betroffen**: `postgres-storage-postgres-0`, `rabbitmq-storage-rabbitmq-0`, `minio-storage-minio-0` nach Namespace-Wechsel oder StorageClass-Änderung.

---

## Workaround 9: SOPS age Key regenerieren

**Problem**: Alter age Key verloren → Production-Secrets nicht entschlüsselbar.

**Lösung**:
```bash
# 1. Neuen Key generieren
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt

# 2. Public Key notieren (Ausgabe: age1...)
cat ~/.config/sops/age/keys.txt

# 3. .sops.yaml aktualisieren
# creation_rules:
#   - path_regex: infrastructure/kubernetes/.*secrets\.yaml$
#     age: <NEUER_PUBLIC_KEY>

# 4. Alle Production-Secrets neu verschlüsseln
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt
for f in infrastructure/kubernetes/*-secrets.yaml; do
  # Plaintext-Version erstellen, dann verschlüsseln
  sops -d "$f" > /tmp/$(basename "$f") 2>/dev/null || true
  sops -e -i "$f"
done

# 5. Secrets im Cluster aktualisieren
for f in infrastructure/kubernetes/*-secrets.yaml; do
  sops -d "$f" | kubectl apply -f -
done
```

---

## Vollständiger Deploy-Ablauf (mit allen Workarounds)

```bash
# === PHASE 0: Cleanup ===
kubectl delete namespace meeting-automation 2>/dev/null

# === PHASE 1: Setup-Script (läuft bis Postgres-Timeout) ===
bash setup-kubernetes.sh || true

# === PHASE 2: Workarounds anwenden ===
# 2a. Local-Path Provisioner
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml
kubectl wait --for=condition=ready pod -l app=local-path-provisioner -n local-path-storage --timeout=30s

# 2b. CoreDNS fixen
kubectl create configmap coredns -n kube-system --from-literal=Corefile='.:53 {
    errors
    health { lameduck 5s }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa { fallthrough in-addr.arpa ip6.arpa }
    prometheus :9153
    forward . /etc/resolv.conf
    cache 30
    loop
    reload
    loadbalance
}' --dry-run=client -o yaml | kubectl apply -f -
kubectl delete pod -n kube-system -l k8s-app=kube-dns
kubectl wait --for=condition=ready pod -n kube-system -l k8s-app=kube-dns --timeout=30s

# 2c. PVCs die hängen bleiben forcieren
kubectl delete pvc -n meeting-automation --all --force 2>/dev/null || true

# 2d. Infrastructure neu starten (PVCs werden neu erstellt)
kubectl delete statefulset postgres rabbitmq minio -n meeting-automation
kubectl apply -f infrastructure/kubernetes/postgres-statefulset.yaml
kubectl apply -f infrastructure/kubernetes/rabbitmq-statefulset.yaml
kubectl apply -f infrastructure/kubernetes/minio-statefulset.yaml
kubectl wait --for=condition=ready pod -l app=postgres -n meeting-automation --timeout=120s

# === PHASE 3: Application Deploy ===
kubectl apply -f infrastructure/kubernetes/backend-deployment.yaml
kubectl apply -f infrastructure/kubernetes/celery-worker-deployment.yaml
kubectl apply -f infrastructure/kubernetes/celery-beat-deployment.yaml
kubectl apply -f infrastructure/kubernetes/n8n-deployment.yaml
kubectl apply -f infrastructure/kubernetes/frontend-deployment.yaml
kubectl apply -f infrastructure/kubernetes/traefik-rbac.yaml
kubectl apply -f infrastructure/kubernetes/traefik-deployment.yaml
kubectl apply -f infrastructure/kubernetes/traefik-middlewares.yaml
kubectl apply -f infrastructure/kubernetes/traefik-ingressroute.yaml

# === PHASE 4: Images laden (falls ErrImageNeverPull) ===
docker save meeting-automation-frontend:latest | docker exec -i desktop-control-plane ctr -n k8s.io images import -
kubectl rollout restart deployment/frontend -n meeting-automation

# === PHASE 5: Wait for all ===
kubectl wait --for=condition=ready pod -l app=backend -n meeting-automation --timeout=120s
kubectl wait --for=condition=ready pod -l app=frontend -n meeting-automation --timeout=120s
kubectl wait --for=condition=ready pod -l app=n8n -n meeting-automation --timeout=120s
kubectl wait --for=condition=ready pod -l app=celery-worker -n meeting-automation --timeout=60s

# === PHASE 6: Post-Setup ===
kubectl exec -i deployment/backend -n meeting-automation -- bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head"
kubectl exec -i statefulset/minio -n meeting-automation -- mc alias set myminio http://localhost:9000 minio_user minio_password_prod
kubectl exec -i statefulset/minio -n meeting-automation -- mc mb myminio/recordings --ignore-existing

# === PHASE 7: Verify ===
kubectl get pods -n meeting-automation
```

---

## Service-Zugriff

```bash
# Frontend
kubectl port-forward deployment/frontend 3000:80 --address 0.0.0.0 -n meeting-automation

# Backend API
kubectl port-forward deployment/backend 8000:8000 --address 0.0.0.0 -n meeting-automation

# n8n UI
kubectl port-forward deployment/n8n 5678:5678 --address 0.0.0.0 -n meeting-automation

# MinIO Console
kubectl port-forward statefulset/minio 9001:9001 --address 0.0.0.0 -n meeting-automation
```

---

## Erwarteter Endzustand

```
NAME                             READY   STATUS
backend-xxx-xxx                  1/1     Running
backend-xxx-xxx                  1/1     Running
celery-beat-xxx-xxx              1/1     Running
celery-worker-xxx-xxx            1/1     Running
frontend-xxx-xxx                 1/1     Running
frontend-xxx-xxx                 1/1     Running
livekit-egress-xxx-xxx           1/1     Running
livekit-server-xxx-xxx           1/1     Running
minio-0                          1/1     Running
n8n-xxx-xxx                      1/1     Running
onlyoffice-xxx-xxx               1/1     Running
postgres-0                       1/1     Running
rabbitmq-0                       1/1     Running
redis-xxx-xxx                    1/1     Running
```

---

## Workaround 10: Backend DB_HOST Environment Variable

**Problem**: Backend pods crashlooped mit `postgres:5432 - no response`. Die `entrypoint.sh` nutzt `DB_HOST="${DB_HOST:-postgres}"` als Default, aber der Service heißt `postgres-staging`.

**Fix**: `DB_HOST` Env-Var auf Backend-Deployment setzen:
```bash
kubectl set env deployment/backend -n meeting-automation-staging DB_HOST=postgres-staging
```

**Root Cause**: `entrypoint.sh` Zeile 3: `DB_HOST="${DB_HOST:-postgres}"` — der pg_isready Health-Check nutzt diesen Wert, während `DATABASE_URL` im Secret korrekt auf `postgres-staging` zeigt.

---

## Workaround 11: LiveKit API Key Length

**Problem**: LiveKit Server crashlooped mit `secret is too short, should be at least 32 characters for security`.

**Fix**: API Key und Secret auf ≥32 Zeichen verlängern:
```yaml
# In livekit-config ConfigMap:
keys:
  meeting-api-key-2026: meeting-api-secret-2026-meeting-automation-staging

# In livekit-secrets Secret:
LIVEKIT_API_KEY: "meeting-api-key-2026"
LIVEKIT_API_SECRET: "meeting-api-secret-2026-meeting-automation-staging"
```

---

## Workaround 12: Redis Password Mismatch

**Problem**: LiveKit und Egress crashlooped mit `WRONGPASS invalid username-password pair`. Das ConfigMap hatte `redis_password_prod`, aber das Secret enthält `redis_password`.

**Fix**: Redis-Passwort in LiveKit-ConfigMap anpassen:
```yaml
redis:
  address: redis-staging:6379
  password: redis_password  # NICHT redis_password_prod
```

**Prüfen**: `kubectl get secret redis-secrets -n meeting-automation-staging -o jsonpath='{.data.password}' | base64 -d`

---

## Workaround 13: Traefik Service Selector Mismatch

**Problem**: Traefik Service hatte keine Endpoints. Service-Selector `app: traefik` matchte nicht mit Pod-Labels (nur `app.kubernetes.io/name: traefik` vorhanden).

**Fix**: Falschen Selector entfernen:
```bash
kubectl patch svc traefik -n kube-system --type=json -p '[{"op":"remove","path":"/spec/selector/app"}]'
```

**Prüfen**: `kubectl get endpoints traefik -n kube-system` → Endpoints müssen sichtbar sein.

---

## Workaround 14: Traefik TargetPort Falsch

**Problem**: Traefik Service mapped Port 80→targetPort 80 und 443→targetPort 443, aber Traefik hört auf `:8000` (web) und `:8443` (websecure).

**Fix**: TargetPorts anpassen:
```bash
kubectl patch svc traefik -n kube-system --type=json -p '[
  {"op":"replace","path":"/spec/ports/0/targetPort","value":8000},
  {"op":"replace","path":"/spec/ports/1/targetPort","value":8443}
]'
```

**Traefik Entrypoints** (aus `--entryPoints.*.address` Args):
- `:8000` = web (HTTP)
- `:8443` = websecure (HTTPS)
- `:8080` = traefik (Dashboard)
- `:9100` = metrics

---

## Workaround 15: Alte TLS-IngressRoutes blockieren CRD-Provider

**Problem**: Traefik loggte `Error configuring TLS: secret meeting-automation-staging/traefik-tls-cert-staging does not exist` und die Routes wurden nicht geladen. Die alte `staging-api-route` nutzte `websecure` EntryPoints mit TLS, aber kein TLS-Secret existierte.

**Fix**: Alte IngressRoutes löschen, neue HTTP-only Route erstellen:
```bash
kubectl delete ingressroute staging-api-route -n meeting-automation-staging
kubectl delete ingressroute staging-redirect-http -n meeting-automation-staging
```

Dann neue HTTP-Only IngressRoute anlegen (siehe `staging-full-route` in .loop.md).

---

## Workaround 16: Staging DB Schema Drift — Missing Stripe Columns

**Problem**: Meeting-Erstellung gibt HTTP 500:
```
asyncpg.exceptions.UndefinedColumnError:
  column clients.stripe_subscription_id does not exist
```

**Root Cause**: Migration `8779f409105a` (add_stripe_ids_to_clients) wurde via `alembic stamp` als angewendet markiert, lief aber nie. Die Migration versucht, 13 nicht-existente Indizes zu droppen (Seiteneffekt der Auto-Generierung). Die Staging-DB wurde via `Base.metadata.create_all()` erstellt — diese erstellt Tabellen aus Modellen, aber nicht die Performance-Indizes aus `g1h2i3j4k5l6`.

**Dokumentation**: `docs/STAGING_DB_SCHEMA_DRIFT_2026-06-22.md`

**Fix (Sichere Migration)**:
```bash
# 1. Sichere Migration erstellen (nur Spalten hinzufügen, keine Index-Drops)
cat > backend/alembic/versions/k1l2m3n4o5p6_add_stripe_columns_safe.py << 'EOF'
"""Add stripe columns to clients (safe, no index drops)"""
from alembic import op
import sqlalchemy as sa

revision = 'k1l2m3n4o5p6'
down_revision = 'j4k5l6m7n8o'

def upgrade():
    op.add_column('clients', sa.Column('stripe_subscription_id', sa.String(), nullable=True))
    op.add_column('clients', sa.Column('stripe_customer_id', sa.String(), nullable=True))

def downgrade():
    op.drop_column('clients', 'stripe_customer_id')
    op.drop_column('clients', 'stripe_subscription_id')
EOF

# 2. Migration auf Pod kopieren
kubectl cp backend/alembic/versions/k1l2m3n4o5p6_add_stripe_columns_safe.py \
  meeting-automation-staging/$(kubectl get pod -n meeting-automation-staging -l app=backend -o jsonpath='{.items[0].metadata.name}'):/app/alembic/versions/

# 3. Migration anwenden
kubectl exec -n meeting-automation-staging $(kubectl get pod -n meeting-automation-staging -l app=backend -o jsonpath='{.items[0].metadata.name}') -- \
  bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head"

# 4. Verifizieren
kubectl exec -n meeting-automation-staging postgres-staging-0 -- \
  psql -U meeting_user -d meeting_db_staging -c "\d clients"
```

**Erwartung**: `stripe_subscription_id` und `stripe_customer_id` erscheinen in der `clients`-Tabelle.

**Verhinderung**: 
- Nie `alembic stamp head` auf frischen Datenbanken verwenden
- Immer `alembic upgrade head` ausführen
- Schema-Verifizierung in Setup-Scripts einbauen
- **Beide Setup-Scripts** (`setup-kubernetes.sh` + `setup-kubernetes-staging.sh`) prüfen jetzt automatisch:
  - Fehlende Stripe-Spalten → werden per `ADD COLUMN IF NOT EXISTS` hinzugefügt
  - Lowercase enum-Werte → werden zu UPPERCASE konvertiert
  - Verwaiste Alembic-Stempel → werden zurückgesetzt
  - MinIO Credentials → werden aus `minio-secrets` gelesen (nicht hardcoded)

---

## Workaround 17: MinIO Credential Mismatch

**Problem**: LiveKit Egress und Backend konnten nicht auf MinIO zugreifen. Die Credentials in den ConfigMaps/Secrets stimmten nicht mit den MinIO Root Credentials überein.

**Root Cause**: 
- `minio-secrets` hat `MINIO_ROOT_PASSWORD: minio_password_staging_2026`
- `backend-secrets` hatte `S3_SECRET_KEY: minio_password_staging` (ohne `_2026`)
- `livekit-configmap` hatte `secret: minio_password_staging` (ohne `_2026`)

**Fix**:
```bash
# 1. Backend Secret aktualisieren
kubectl get secret backend-secrets-staging -n meeting-automation-staging -o json | \
  python3 -c "import sys,json,base64; d=json.load(sys.stdin); d['data']['S3_SECRET_KEY']=base64.b64encode(b'minio_password_staging_2026').decode(); print(json.dumps(d))" | \
  kubectl apply -f -

# 2. LiveKit Egress ConfigMap aktualisieren
kubectl get configmap livekit-config -n meeting-automation-staging -o yaml | \
  sed 's/secret: minio_password_staging/secret: minio_password_staging_2026/g' | \
  kubectl apply -f -

# 3. Pods neu starten
kubectl rollout restart deployment/backend -n meeting-automation-staging
kubectl rollout restart deployment/celery-worker-staging -n meeting-automation-staging
kubectl rollout restart deployment/livekit-egress -n meeting-automation-staging
```

**Verhinderung**: 
- MinIO Credentials nie hardcoden → aus `minio-secrets` lesen
- Setup-Scripts nutzen jetzt `kubectl get secret minio-secrets` für S3 Bucket Creation
- LiveKit ConfigMap nutzt Platzhalter `__MINIO_USER__`/`__MINIO_PASS__`

---

## Workaround 18: Staging DB Schema Drift — Missing Speakers + Recordings Columns

**Problem**: Meeting-Pipeline (Recording → Transcription → Speaker ID) schlägt fehl:
```
column recordings.access_policy does not exist
```

**Root Cause**: 4 disjunkte Alembic-Branches (`08439ee30c73`, `8779f409105a`, `d5e6f7a8b9c0`, `l2m3n4o5p6q7`) wurden nie gemerget. `alembic upgrade head` folgt nur der Hauptchain. Die Branchen `c3fe9e232652`→`c8d9e0f1a2b3` (access_policy) und `8a1b2c3d4e5f` (speaker profile columns) sind nicht mit der Hauptchain verbunden.

**Fehlende Spalten:**

| Tabelle | Spalten | Anzahl |
|---------|---------|--------|
| `speakers` | client_id, resolved_name, embedding, sample_count, mapping_confidence, mapping_method, source | 7 |
| `recordings` | access_policy, error_message, egress_id | 3 |

**Dokumentation**: `docs/STAGING_DB_SCHEMA_DRIFT_2026-06-22.md` (Phase 2)

**Fix (Migration `m1n2o3p4q5r6`)**:
```bash
# 1. Migration erstellen (IF NOT EXISTS Guards)
# Datei: backend/alembic/versions/m1n2o3p4q5r6_add_missing_speakers_recordings_columns.py

# 2. Zu ALLEN Backend-Pods kopieren (nicht nur erster!)
BACKEND_PODS=$(kubectl get pods -n meeting-automation-staging -l app=backend -o jsonpath='{.items[*].metadata.name}')
for pod in $BACKEND_PODS; do
    kubectl cp backend/alembic/versions/m1n2o3p4q5r6_*.py meeting-automation-staging/$pod:/app/alembic/versions/
done

# 3. Migration anwenden
kubectl exec -n meeting-automation-staging $(kubectl get pod -l app=backend -o jsonpath='{.items[0].metadata.name}') -- \
  bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head"

# 4. Verifizieren
kubectl exec -n meeting-automation-staging postgres-staging-0 -- \
  psql -U meeting_user -d meeting_db_staging -c "\d speakers"
# → 11 Spalten (vorher 4)
```

**Verhinderung**:
- Setup-Script gefixt: Migrationen werden zu ALLEN Backend-Pods kopiert (siehe Workaround 19)
- IF NOT EXISTS Guards verhindern Fehler bei doppelter Ausführung
- Nie manuelle SQL-Änderungen verwenden — immer Alembic-Migrationen

---

## Workaround 19: Multi-Replica Migration Copy — kubectl cp + exec Pod Mismatch

**Problem**: `kubectl cp` sendet die Datei an Pod A, aber `kubectl exec` führt `alembic upgrade head` auf Pod B aus. Die Migration fehlt auf Pod B → `alembic upgrade head` überspringt sie.

**Root Cause**: `kubectl get pod -l app=backend -o jsonpath='{.items[0].metadata.name}'` liefert immer den ersten Pod. Bei 2+ Replicas sind `kubectl cp` (sendet an Pod A) und `kubectl exec` (führt auf Pod B aus) möglicherweise nicht derselbe Pod.

**Fix in beiden Setup-Scripts**:
```bash
# ALLE Pods auswählen (nicht nur [0])
BACKEND_PODS=$(kubectl get pods -n $NS -l app=backend -o jsonpath='{.items[*].metadata.name}')
for pod in $BACKEND_PODS; do
    kubectl cp <migration-file> $NS/$pod:/app/alembic/versions/
    echo "Migration copied to $pod"
done
```

**Multi-Version-Grep**: Setup-Scripts prüfen jetzt mehrere gültige Versionen, um DBs nach Alembic-Stamp korrekt zu erkennen:
```bash
# Früher: nur eine Version
if [[ "$VERSION" == *"3cb95dfba7be"* ]]; then ...

# Jetzt: mehrere Versionen
if [[ "$VERSION" == *"3cb95dfba7be"* ]] || [[ "$VERSION" == *"m1n2o3p4q5r6"* ]]; then ...
```

**Verhinderung**:
- Immer ALLE Pods einer App iterieren, nicht nur den ersten
- Multi-Version-Grep für Alembic-Stamps nach `alembic stamp`
- Beide Setup-Scripts (`setup-kubernetes.sh` + `setup-kubernetes-staging.sh`) nutzen dieses Muster

---

## Workaround 20: DATABASE_SCHEMA.md Ungenau — Komplett Neu Geschrieben

**Problem**: `docs/DATABASE_SCHEMA.md` enthielt veraltete/ungenaue Spaltenzahlen und referenzierte Spalten, die nicht existieren.

**Root Cause**: Schema wurde während der Entwicklung geändert, aber die Doku nie aktualisiert. Alembic-Branches wurden nie gemerget → Schema divergierte.

**Fix**: `docs/DATABASE_SCHEMA.md` komplett neu geschrieben mit tatsächlichen Spaltenzahlen aller 9 Tabellen:

| Tabelle | Spalten | Enums |
|---------|---------|-------|
| `meetings` | 20 | `meetingstatus_v2` (PLANNED, IN_PROGRESS, COMPLETED, CANCELLED, ARCHIVED) |
| `recordings` | 12 | `recordingstatus` (IDLE, RECORDING, PROCESSING, COMPLETED, FAILED), `recordingformat` (MP4, WEBM, OGG, WAV) |
| `transcript_segments` | 11 | `segmentstatus` (PENDING, TRANSCRIBING, COMPLETED, FAILED), `segmenttype` (SPEAKER_TURN, INTERACTION, SYSTEM) |
| `speakers` | 11 | — |
| `action_items` | 12 | `actionstatus` (PENDING, IN_PROGRESS, COMPLETED, CANCELLED, OVERDUE), `actionpriority` (LOW, MEDIUM, HIGH, CRITICAL, BLOCKER), `actioncategory` (TODO, DECISION, QUESTION, INFO, FOLLOW_UP, RISK) |
| `meeting_documents` | 9 | — |
| `clients` (billing) | 8+ | `subscriptionplan` (FREE, BASIC, PRO, ENTREPRISE), `subscriptionstatus` (ACTIVE, DISABLED, SUSPENDED, CANCELLED, PAST_DUE, TRIAL) |
| `invitation_tokens` | 7 | — |
| `users` | 13 | `userrole` (USER, ADMIN, SYSTEM_ADMIN) |

**Verhinderung**:
- Schema-Änderungen immer über Alembic-Migrationen (nie manuell)
- `docs/DATABASE_SCHEMA.md` nach jedem Schema-Update aktualisieren
- Alembic-Branches regelmäßig mergen, um Drift zu vermeiden

---

## Workaround 21: LiveKit PUBLIC_URL — Internal DNS Not Reachable From Browser

**Problem**: Frontend kann sich nicht mit LiveKit verbinden. Der `serverUrl` im Token-Response ist `ws://livekit-server:7880` — ein interner Cluster-DNS-Name, den der Browser nicht auflösen kann.

**Root Cause**: `LIVEKIT_PUBLIC_URL` in `backend-config` war auf den internen Cluster-Service gesetzt (`ws://livekit-server:7880`). Der Browser (extern) braucht eine erreichbare URL.

**Fix**:
```bash
# 1. LiveKit Service auf NodePort umstellen
kubectl patch svc livekit-server -n $NS -p '{"spec":{"type":"NodePort"}}'

# 2. Externe IP als LIVEKIT_PUBLIC_URL setzen
kubectl get configmap backend-config -n $NS -o json | \
  python3 -c "
import sys, json
cm = json.load(sys.stdin)
cm['data']['LIVEKIT_PUBLIC_URL'] = 'ws://$(hostname -I | awk '{print $1}'):30087'
print(json.dumps(cm))
" | kubectl apply -f -

# 3. Backend neustarten
kubectl rollout restart deployment/backend -n $NS
```

**ICE/NAT-Konfiguration**:
- LiveKit erkennt die externe IP via STUN (`use_external_ip: true`)
- UDP ICE-Ports (7881-7890) müssen vom Host in den Cluster forwarded werden
- In Kind: nur TCP NodePorts verfügbar, UDP-Forwarding erfordert Kind-Config-Änderung
- In Produktion: Cloud-LoadBalancer oder UDP-Port-Forwarding konfigurieren

**Kind-Limitierung**: Kind forwarded nur TCP-Ports (6443 für K8s API). UDP ICE-Ports 7881-7890 sind intern im Cluster nicht vom Host erreichbar. WebRTC-Verbindung vom Browser funktioniert nur mit Production-Setup oder manuellem UDP-Port-Forwarding.

**Verhinderung**:
- `LIVEKIT_PUBLIC_URL` muss eine vom Browser erreichbare URL sein (nie interner Cluster-DNS)
- In Production: Domain + TLS für `wss://livekit.yourhost.com` verwenden
- ICE-Ports in Firewall/Security-Group freigeben
