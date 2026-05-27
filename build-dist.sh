#!/bin/bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Konfiguration
DIST_DIR="/tmp/meeting-automation-dist"
ORIGINAL_DIR="$(pwd)"

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}   Meeting Automation - Distribution Builder${NC}"
echo -e "${BLUE}============================================================${NC}"

# 1. Prüfen, ob wir im richtigen Verzeichnis sind
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Fehler: Keine docker-compose.yml im aktuellen Verzeichnis${NC}"
    exit 1
fi

# 2. Distribution-Verzeichnis vorbereiten
echo -e "${YELLOW}[1/5] Vorbereite Distributionsverzeichnis...${NC}"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# 3. Notwendige Dateien kopieren
echo -e "${YELLOW}[2/5] Kopiere Konfigurationsdateien...${NC}"
cp "$ORIGINAL_DIR/docker-compose.yml" "$DIST_DIR/"
cp "$ORIGINAL_DIR/setup-system.sh" "$DIST_DIR/"
cp "$ORIGINAL_DIR/.env" "$DIST_DIR/" 2>/dev/null && echo "  → .env kopiert" || echo "  → Kein .env gefunden"
cp "$ORIGINAL_DIR/README.md" "$DIST_DIR/" 2>/dev/null || echo "  → Kein README.md"

# 4. n8n Workflows kopieren
if [ -d "$ORIGINAL_DIR/n8n/workflows" ]; then
    echo -e "${YELLOW}[3/5] Kopiere n8n Workflows...${NC}"
    mkdir -p "$DIST_DIR/n8n"
    cp -r "$ORIGINAL_DIR/n8n/workflows" "$DIST_DIR/n8n/"
    echo "  → Workflows kopiert"
else
    echo -e "${YELLOW}  → Keine n8n Workflows gefunden${NC}"
fi

# 5. Docker Images exportieren
echo -e "${YELLOW}[4/5] Exportiere Docker Images...${NC}"

# Prüfen, ob Images existieren
if docker image inspect meeting-automation-backend:latest &>/dev/null; then
    docker save meeting-automation-backend:latest -o "$DIST_DIR/backend.tar"
    echo "  → backend.tar gespeichert"
else
    echo -e "${RED}  → Fehler: meeting-automation-backend:latest nicht gefunden${NC}"
    exit 1
fi

if docker image inspect meeting-automation-celery-worker:latest &>/dev/null; then
    docker save meeting-automation-celery-worker:latest -o "$DIST_DIR/celery-worker.tar"
    echo "  → celery-worker.tar gespeichert"
else
    echo -e "${RED}  → Fehler: meeting-automation-celery-worker:latest nicht gefunden${NC}"
    exit 1
fi

if docker image inspect meeting-automation-celery-beat:latest &>/dev/null; then
    docker save meeting-automation-celery-beat:latest -o "$DIST_DIR/celery-beat.tar"
    echo "  → celery-beat.tar gespeichert"
else
    echo -e "${RED}  → Fehler: meeting-automation-celery-beat:latest nicht gefunden${NC}"
    exit 1
fi

if docker image inspect meeting-automation-frontend:v1.0.0 &>/dev/null; then
    docker save meeting-automation-frontend:v1.0.0 -o "$DIST_DIR/frontend.tar"
    echo "  → frontend.tar gespeichert"
else
    echo -e "${RED}  → Fehler: meeting-automation-frontend:v1.0.0 nicht gefunden${NC}"
    exit 1
fi

# 6. Versionsdatei erstellen
echo -e "${YELLOW}[5/5] Erstelle Versionsdatei...${NC}"
echo "Build: $(date '+%Y-%m-%d %H:%M:%S')" > "$DIST_DIR/VERSION"
echo "Image: meeting-automation-backend:latest" >> "$DIST_DIR/VERSION"
docker inspect meeting-automation-backend:latest --format='Image ID: {{.Id}}' >> "$DIST_DIR/VERSION" 2>/dev/null || echo "Image ID: nicht verfügbar" >> "$DIST_DIR/VERSION"

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Distribution fertig erstellt!${NC}"
echo -e "${GREEN}  Verzeichnis: $DIST_DIR${NC}"
echo -e "${GREEN}  Größe: $(du -sh "$DIST_DIR" | cut -f1)${NC}"
echo -e "${GREEN}============================================================${NC}"
ls -lh "$DIST_DIR/"
