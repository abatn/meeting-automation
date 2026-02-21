#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🚀 Starte finalen System-Fix...${NC}"

# 1. Stoppe alle Container
echo "🛑 Stoppe und lösche alle Container und Volumes..."
docker-compose down -v

# 2. Stelle sicher, dass n8n-Workflows Verzeichnis existiert
mkdir -p n8n/workflows
chmod -R 777 n8n

# 3. Starte Datenbank-Service zuerst
echo "🐘 Starte PostgreSQL..."
docker-compose up -d postgres
echo "Warte auf Datenbank-Bereitschaft..."
sleep 10

# 4. Erstelle n8n_db manuell
echo "🛠 Erstelle n8n_db Datenbank..."
docker exec -i $(docker-compose ps -q postgres) psql -U meeting_user -d meeting_db -c "CREATE DATABASE n8n_db;" || echo "Datenbank existiert bereits."
docker exec -i $(docker-compose ps -q postgres) psql -U meeting_user -d meeting_db -c "GRANT ALL PRIVILEGES ON DATABASE n8n_db TO meeting_user;" || true

# 5. Baue und starte alle anderen Services
echo "🏗 Baue Images neu (ohne Cache) und starte Services..."
docker-compose build --no-cache
docker-compose up -d

# 6. Warte auf n8n
echo "⏳ Warte auf n8n Initialisierung..."
sleep 20

# 7. System-Check
echo -e "${GREEN}🔍 Überprüfe Service-Status...${NC}"
docker-compose ps

SERVICES=("backend" "frontend" "postgres" "redis" "rabbitmq" "minio" "n8n" "celery-worker" "celery-beat")
FAILED=0

for service in "${SERVICES[@]}"; do
    if docker-compose ps "$service" | grep -q "Up"; then
        echo -e "✅ $service: [RUNNING]"
    else
        echo -e "❌ $service: [FAILED]"
        echo "Logs for $service:"
        docker-compose logs "$service" --tail=20
        FAILED=1
    fi
done

echo -e "\n${GREEN}🌐 Erreichbarkeit der Dienste:${NC}"
echo "--------------------------------------------------"
echo "Frontend:      http://localhost:3000"
echo "Backend API:   http://localhost:8000/api/docs"
echo "n8n UI:        http://localhost:5678 (User: admin@example.com / admin_password)"
echo "MinIO Console: http://localhost:9001"
echo "RabbitMQ:      http://localhost:15672"
echo "--------------------------------------------------"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎯 FINALER FIX ERFOLGREICH! Alle Systeme laufen.${NC}"
else
    echo -e "${RED}⚠️ Einige Dienste sind nicht korrekt gestartet. Bitte Logs prüfen.${NC}"
    exit 1
fi