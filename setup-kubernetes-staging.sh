#!/bin/bash
set -e

# Colors for professional output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

NAMESPACE="meeting-automation-staging"
POSTGRES_POD="postgres-staging-0"
DB_USER="meeting_user"
DB_NAME="meeting_db_staging"
INFRA_DIR="./infrastructure/kubernetes/staging"

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   Meeting Automation - Staging K8s Initialization  ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}   Namespace : ${NAMESPACE}${NC}"
echo -e "${BLUE}   Database  : ${DB_NAME}${NC}"
echo -e "${BLUE}====================================================${NC}"

# 0. Prüfe kubectl
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed or not in PATH.${NC}"
    exit 1
fi

# Setze KUBECONFIG falls Datei vorhanden
if [ -f "./kubeconfig-staging.txt" ]; then
    export KUBECONFIG="$(pwd)/kubeconfig-staging.txt"
    echo -e "${GREEN}Using kubeconfig: ./kubeconfig-staging.txt${NC}"
fi

# Prüfe ob staging-cluster Context existiert
if ! kubectl config get-contexts 2>/dev/null | grep -q "staging-cluster"; then
    echo -e "${RED}Error: Context 'staging-cluster' not found in kubeconfig.${NC}"
    kubectl config get-contexts 2>/dev/null || true
    exit 1
fi
kubectl config use-context staging-cluster > /dev/null
echo -e "${GREEN}Context: staging-cluster${NC}"

# 1. Namespace sicherstellen
echo -e "${YELLOW}[1/7] Prüfe Namespace '${NAMESPACE}'...${NC}"
if kubectl get namespace "${NAMESPACE}" &> /dev/null; then
    echo -e "${GREEN}Namespace existiert bereits.${NC}"
else
    kubectl apply -f "${INFRA_DIR}/namespace.yaml"
    echo -e "${GREEN}Namespace erstellt.${NC}"
fi

# 2. Warte auf PostgreSQL (muss Running sein)
echo -e "${YELLOW}[2/7] Prüfe PostgreSQL Pod '${POSTGRES_POD}'...${NC}"
if ! kubectl wait --for=condition=ready "pod/${POSTGRES_POD}" \
    -n "${NAMESPACE}" --timeout=120s 2>/dev/null; then
    echo -e "${RED}PostgreSQL Pod ist nicht bereit. Prüfe:${NC}"
    echo -e "  kubectl get pods -n ${NAMESPACE}"
    exit 1
fi
echo -e "${GREEN}PostgreSQL ist bereit.${NC}"

# 3. Warte auf Backend (muss Running sein für alembic)
echo -e "${YELLOW}[3/7] Prüfe Backend Deployment...${NC}"
BACKEND_POD=$(kubectl get pods -n "${NAMESPACE}" -l app=backend \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -z "${BACKEND_POD}" ]; then
    echo -e "${RED}Kein Backend Pod gefunden in Namespace ${NAMESPACE}.${NC}"
    echo -e "  kubectl get pods -n ${NAMESPACE}"
    exit 1
fi
echo -e "${GREEN}Backend Pod: ${BACKEND_POD}${NC}"

# 4. Datenbankzustand prüfen und Migrationen durchführen
echo -e "${YELLOW}[4/7] Prüfe Datenbankzustand für Alembic Migrationen...${NC}"

TABLE_EXISTS=$(kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
    psql -U "${DB_USER}" -d "${DB_NAME}" -tAc \
    "SELECT EXISTS (
        SELECT FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'users'
    );")

# Prüfe ob alembic_version einen Eintrag hat (möglicherweise verwaister Stempel)
ALEMBIC_STAMPED=$(kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
    psql -U "${DB_USER}" -d "${DB_NAME}" -tAc \
    "SELECT EXISTS (
        SELECT FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'alembic_version'
    );" 2>/dev/null || echo "f")

if [ "${TABLE_EXISTS}" = "t" ]; then
    echo -e "${BLUE}Tabellen bereits vorhanden. Führe ausstehende Migrationen durch (upgrade head)...${NC}"
    # upgrade head (nicht stamp): wendet nur neue Migrationen an, überspringt bereits angewendete
    kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
        bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head"
    echo -e "${GREEN}Migrationen aktuell (upgrade head).${NC}"
else
    # Verwaister Stempel: alembic_version existiert aber keine echten Tabellen
    # (passiert wenn create_staging_schema.sql nur stempelte, Tabellen aber gelöscht wurden)
    if [ "${ALEMBIC_STAMPED}" = "t" ]; then
        echo -e "${YELLOW}Verwaister Alembic-Stempel gefunden (Tabellen fehlen). Setze zurück...${NC}"
        kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
            psql -U "${DB_USER}" -d "${DB_NAME}" -c \
            "DELETE FROM alembic_version;" > /dev/null
        echo -e "${GREEN}Alembic-Stempel zurückgesetzt.${NC}"
    fi

    echo -e "${YELLOW}Führe Migrationen durch...${NC}"

    # Schritt 4a: Migrationen bis einschließlich e9dd04c9d6f1 (erstellt action_suggestions)
    echo -e "${BLUE}  Schritt 4a: Migrationen bis e9dd04c9d6f1...${NC}"
    kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
        bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade e9dd04c9d6f1"

    # Prüfe ob action_suggestions existiert
    AS_EXISTS=$(kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
        psql -U "${DB_USER}" -d "${DB_NAME}" -tAc \
        "SELECT EXISTS (
            SELECT FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'action_suggestions'
        );")

    if [ "${AS_EXISTS}" = "t" ]; then
        # Schritt 4b: Fehlende 'language'-Spalte manuell hinzufügen
        # Bug: e9dd04c9d6f1 erstellt action_suggestions ohne 'language',
        #      aber 4fb76575fee0 erwartet sie (ALTER COLUMN ... nullable=False).
        echo -e "${BLUE}  Schritt 4b: Füge fehlende 'language'-Spalte hinzu (Alembic Bug Fix)...${NC}"
        kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
            psql -U "${DB_USER}" -d "${DB_NAME}" -c \
            "ALTER TABLE action_suggestions
             ADD COLUMN IF NOT EXISTS language VARCHAR(10)
             DEFAULT 'en' NOT NULL;" > /dev/null
        echo -e "${GREEN}  Spalte 'language' sichergestellt.${NC}"
    else
        echo -e "${YELLOW}  action_suggestions nicht gefunden (nicht auf diesem Migrationspfad). Überspringe Fix.${NC}"
    fi

    # Schritt 4c: Restliche Migrationen bis head
    echo -e "${BLUE}  Schritt 4c: Restliche Migrationen bis head...${NC}"
    kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
        bash -c "export PYTHONPATH=/app && cd /app && alembic upgrade head"

    echo -e "${GREEN}Alle Migrationen erfolgreich.${NC}"
fi

# 5. n8n Hilfstabelle initialisieren (wie in setup-kubernetes.sh)
echo -e "${YELLOW}[5/7] Initialisiere n8n Hilfstabelle (n8n_meetings)...${NC}"
kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
    psql -U "${DB_USER}" -d "${DB_NAME}" -c "
CREATE TABLE IF NOT EXISTS n8n_meetings (
    id SERIAL PRIMARY KEY,
    meeting_id VARCHAR(255) NOT NULL,
    title TEXT,
    start_time VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);" > /dev/null
echo -e "${GREEN}n8n_meetings Tabelle sichergestellt.${NC}"

# 6. System-User und Rollen seeden
echo -e "${YELLOW}[6/7] Seede System-User und Rollen (seed_users.py)...${NC}"
kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
    bash -c "export PYTHONPATH=/app && cd /app && python scripts/seed_users.py" \
    || echo -e "${RED}Warnung: Seeding fehlgeschlagen oder User bereits vorhanden.${NC}"

# Aktualisiere e2e-test-user Secret mit korrekten Credentials
echo -e "${YELLOW}   Aktualisiere e2e-test-user Secret...${NC}"
kubectl create secret generic e2e-test-user \
    --namespace "${NAMESPACE}" \
    --from-literal=E2E_TEST_USER_EMAIL="e2e-tester@staging.meeting.tn" \
    --from-literal=E2E_TEST_USER_PASSWORD="Password123!" \
    --dry-run=client -o yaml | kubectl apply -f - > /dev/null
echo -e "${GREEN}e2e-test-user Secret gesetzt.${NC}"

# 7. S3 Bucket erstellen
echo -e "${YELLOW}[7/7] Erstelle S3 Bucket 'meeting-recordings-staging'...${NC}"
kubectl exec -i "deployment/backend" -n "${NAMESPACE}" -- \
    bash -c "export PYTHONPATH=/app && cd /app && python -" < scripts/create_s3_bucket.py \
    || echo -e "${RED}Warnung: S3 Bucket Erstellung fehlgeschlagen oder existiert bereits.${NC}"

# Abschluss-Check
echo ""
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}   STAGING SETUP ABGESCHLOSSEN!                    ${NC}"
echo -e "${BLUE}====================================================${NC}"
echo ""

echo -e "${YELLOW}Tabellen-Übersicht:${NC}"
kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
    psql -U "${DB_USER}" -d "${DB_NAME}" -c \
    "SELECT COUNT(*) AS tabellen_gesamt FROM information_schema.tables
     WHERE table_schema = 'public';" 2>/dev/null || true

echo ""
echo -e "${YELLOW}User-Übersicht:${NC}"
kubectl exec -i "${POSTGRES_POD}" -n "${NAMESPACE}" -- \
    psql -U "${DB_USER}" -d "${DB_NAME}" -c \
    "SELECT email, status, is_superuser FROM users ORDER BY created_at;" 2>/dev/null || true

echo ""
echo -e "${GREEN}Nächste Schritte:${NC}"
echo -e "  kubectl get pods -n ${NAMESPACE}"
echo -e "  kubectl port-forward svc/backend 8080:8000 -n ${NAMESPACE}"
echo -e "  curl http://localhost:8080/health"
echo -e "  ./scripts/run-e2e-tests-fixed.sh --env staging \\"
echo -e "      --user-email e2e-tester@staging.meeting.tn \\"
echo -e "      --user-pass 'Password123!'"
echo ""
