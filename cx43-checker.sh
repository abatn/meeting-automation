#!/bin/bash
# CX43 Availability Checker — Multi-Location EU
# Prüft alle 15 Minuten ob CX43 in EU-Standorten verfügbar ist
# Erstellt den Server automatisch sobald verfügbar

TOKEN="43jLu3ToLmuOSAfjb6ey6ONV48KBG8YkwnwxRTSwKXaDWsW2tDCkxnX6SWefX2dQ"
SERVER_NAME="meeting-automation-mvp"
SERVER_TYPE="cx43"
IMAGE="ubuntu-24.04"
SSH_KEY="meeting-automation-key"
LOG_FILE="/home/opc/meeting-automation/cx43-check.log"
INTERVAL=900  # 15 Minuten

# EU-Standorte die geprüft werden (Reihenfolge = Priorität)
LOCATIONS=("nbg1" "fsn1" "hel1")

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_and_create() {
    log "Prüfe CX43 Verfügbarkeit in EU: ${LOCATIONS[*]}..."

    # API-Abfrage
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer $TOKEN" \
        "https://api.hetzner.cloud/v1/server_types/116")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | head -n -1)

    if [ "$HTTP_CODE" != "200" ]; then
        log "FEHLER: API-Antwort $HTTP_CODE"
        return 1
    fi

    # Verfügbaren Standort finden (nach Priorität)
    AVAILABLE_LOCATION=$(echo "$BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
locations = ['nbg1', 'fsn1', 'hel1']
for target in locations:
    for loc in data['server_type']['locations']:
        if loc['name'] == target and loc['available']:
            print(target)
            sys.exit(0)
print('')
")

    if [ -n "$AVAILABLE_LOCATION" ]; then
        log "*** CX43 VERFUEGBAR in $AVAILABLE_LOCATION! Erstelle Server... ***"

        RESULT=$(hcloud server create \
            --name "$SERVER_NAME" \
            --type "$SERVER_TYPE" \
            --image "$IMAGE" \
            --location "$AVAILABLE_LOCATION" \
            --ssh-key "$SSH_KEY" 2>&1)

        if echo "$RESULT" | grep -q "error"; then
            log "FEHLER beim Server-Erstellen: $RESULT"
            return 1
        fi

        log "Server erfolgreich erstellt in $AVAILABLE_LOCATION!"
        log "$RESULT"

        sleep 5
        IP=$(hcloud server describe "$SERVER_NAME" -o json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data['server']['public_net']['ipv4']['ip'])
" 2>/dev/null)

        if [ -n "$IP" ]; then
            log "========================================="
            log "SERVER ERSTELLT!"
            log "Standort: $AVAILABLE_LOCATION"
            log "IP: $IP"
            log "SSH: ssh root@$IP"
            log "========================================="
        fi

        exit 0
    else
        log "CX43 nicht verfügbar in EU. Nächste Prüfung in 15 Min."
    fi
}

log "========================================="
log "CX43 Monitor gestartet (Multi-Location)"
log "Ziel: $SERVER_TYPE"
log "Standorte: ${LOCATIONS[*]}"
log "Intervall: $((INTERVAL / 60)) Minuten"
log "Log: $LOG_FILE"
log "========================================="

while true; do
    check_and_create
    sleep "$INTERVAL"
done
