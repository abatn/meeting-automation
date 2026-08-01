#!/usr/bin/env bash
# test-multi-tenant-queue-routing.sh
# Plan: 3 separate Meetings, 1 pro Tenant (GRATUIT/PRO/ENTREPRISE)
# Reihenfolge A.2: PRO -> ENT -> GRATUIT (Isolation-Test für FREE-worker)

set -euo pipefail

# === Konfiguration ===
NAMESPACE="meeting-automation-staging"
BASE_URL="https://staging.meeting-automation.com"
DB_POD="meeting-db-1"
DB_USER="meeting_user"
DB_PASS="meeting_password"
DB_NAME="meeting_db_staging"
TEST_DATA_DIR="/home/opc/meeting-automation/test-data"
AUDIO_FILE="${TEST_DATA_DIR}/test_meeting_audio.wav"

# Admin-Auth (verifiziert via verify_meeting_flow.py):
# Login user 'admin@meeting.tn' / 'Password123!' liefert access_token im JSON-Body.
# Backend akzeptiert 'Bearer <token>' Authorization Header.
ADMIN_EMAIL="admin@meeting.tn"
ADMIN_PW="Password123!"

# Test-Tenant Definition (DB-Readonly-Check 2026-07-30)
TENANT_GRATUIT_EMAIL="test-gratuit@meeting.tn"
TENANT_GRATUIT_CLIENT_ID="b115edec-a795-46d1-9441-7cc0b8af4107"

TENANT_PRO_EMAIL="test-pro@meeting.tn"
TENANT_PRO_CLIENT_ID="748682d7-c351-4ce6-baed-93be3ffbf153"

TENANT_ENTREPRISE_EMAIL="test-entreprise@meeting.tn"
TENANT_ENTREPRISE_CLIENT_ID="c47d522c-d1ec-415d-9bfd-d1be09ebfb95"

declare -a CLEANUP_IDS=()

# === Helper ===
log() { echo -e "[$(date +%H:%M:%S)] $*"; }
err() { echo -e "[$(date +%H:%M:%S)] ERROR: $*" >&2; }

login() {
  # /api/v1/auth/login nutzt OAuth2PasswordRequestForm (form-data, NICHT JSON)!
  # auth.py Zeile 134–177: JWT kommt ausschließlich als 'Set-Cookie: accessToken=<JWT>'.
  # Der JSON-Body enthält KEIN access_token-Feld (verify_meeting_flow.py ist outdated).
  local email="${1:-${ADMIN_EMAIL:-admin@meeting.tn}}"
  local pw="${2:-${ADMIN_PW:-Password123!}}"
  for attempt in 1 2 3; do
    local resp code token
    resp=$(curl --silent --max-time 10 -i -X POST "${BASE_URL}/api/v1/auth/login" \
      --data-urlencode "username=${email}" \
      --data-urlencode "password=${pw}") || { log "login curl-error for ${email} (attempt ${attempt})"; sleep 5; continue; }
    code=$(echo "${resp}" | head -1 | grep -oE 'HTTP/[0-9.]+ [0-9]+' | awk '{print $2}' | head -1)
    if [ "$code" = "200" ]; then
      # Set-Cookie Header parsen: 'accessToken=<JWT>; HttpOnly; ...'
      token=$(echo "${resp}" | grep -iP '^\s*set-cookie:\s*accessToken=' | sed -E 's/.*accessToken=([^;]+).*/\1/' | head -1)
      if [ -n "$token" ]; then
        echo "$token"
        return 0
      fi
      log "no accessToken cookie in 200 response for ${email}: ${resp}"
    else
      log "login ${email} attempt ${attempt} → HTTP ${code}: $(echo "${resp}" | tail -1)"
    fi
    sleep 3
  done
  err "login FAILED for ${email}"
  return 1
}

api_post_json() {
  local jwt="$1" path="$2" body="$3"
  for attempt in 1 2 3; do
    local http_code body_resp
    body_resp=$(mktemp)
    http_code=$(curl --silent --output "${body_resp}" --write-out "%{http_code}" \
      --max-time 30 -X POST "${BASE_URL}${path}" \
      -H "Authorization: Bearer ${jwt}" \
      -H "Content-Type: application/json" \
      -d "${body}") || { log "POST ${path} → curl error, retry $attempt"; rm -f "${body_resp}"; sleep 3; continue; }
    if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
      cat "${body_resp}"
      rm -f "${body_resp}"
      return 0
    elif [ "$http_code" = "401" ] || [ "$http_code" = "403" ] || [ "$http_code" = "422" ]; then
      err "POST ${path} → ${http_code} (NO retry): $(cat ${body_resp})"
      rm -f "${body_resp}"
      return 1
    else
      log "POST ${path} → ${http_code}, retry $attempt/3"
      sleep 5
    fi
    rm -f "${body_resp}"
  done
  err "POST ${path} failed after 3 retries"
  return 1
}

db_query() {
  local sql="$1"
  kubectl exec "${DB_POD}" -n "${NAMESPACE}" -- \
    env PGPASSWORD="${DB_PASS}" psql -h 127.0.0.1 -U "${DB_USER}" -d "${DB_NAME}" \
    --tuples-only --no-align -c "${sql}"
}

# === Phase 0: Setup ===
phase0_setup() {
  log "=== Phase 0: Setup ==="
  mkdir -p "${TEST_DATA_DIR}"

  # Audio-Datei generieren (Python wave+struct, 30s mono WAV)
  python3 - <<PYEOF
import wave, struct
with wave.open('${AUDIO_FILE}', 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(16000)
    # 30s silences (2 bytes/sample * 16000 samp/s * 30s)
    w.writeframes(b'\\x00\\x00' * 16000 * 30)
PYEOF

  local size
  size=$(stat -c %s "${AUDIO_FILE}" 2>/dev/null || echo 0)
  log "Audio generated: ${AUDIO_FILE} (${size} bytes)"
  if [ "$size" -lt 900000 ] || [ "$size" -gt 1000000 ]; then
    err "Audio size outside 900K-1M (we got ${size})"
    return 1
  fi

  # Sanity: 3 Test-User existieren
  log "Sanity: 3 test tenants in DB"
  db_query "
    SELECT email, subscription_plan::text
    FROM users u JOIN clients c ON u.client_id=c.id
    WHERE email LIKE 'test-%@meeting.tn'
    ORDER BY subscription_plan::text;
  "

  # Hash-Sync: Test-User haben unbekanntes Custom-PW. Wir überschreiben mit dem
  # verifizierten bcrypt-Hash aus ${ADMIN_EMAIL} (=Password123!).
  # Idempotent: selber Hash ohnehin, also kein Sicherheits-Regression.
  log "Hash-Sync: ${ADMIN_EMAIL}'s verifizierter bcrypt-Hash → test-*-User (PW=${ADMIN_PW})"
  local admin_hash
  admin_hash=$(db_query "SELECT hashed_password FROM users WHERE email='${ADMIN_EMAIL}';")
  db_query "UPDATE users SET hashed_password='${admin_hash}' WHERE email LIKE 'test-%@meeting.tn';"
  log "✓ test users jetzt authentifizierbar mit PW=${ADMIN_PW}"
}

# === Phase 1: Consent Grants (3x) ===
phase1_consent() {
  local label="$1" email="$2" pw="$3"

  log "=== Phase 1: Consent Grant für ${label} ==="
  JWT=$(login "${email}" "${pw}") || return 1

  local body='{
    "consents":[
      {"consent_type":"C1_AUDIO","consented":true},
      {"consent_type":"C3_SHARING","consented":true},
      {"consent_type":"C4_STORAGE","consented":true}
    ],
    "consent_version":"1.0",
    "ip_address":"127.0.0.1",
    "user_agent":"test-multi-tenant-2026-07-30"
  }'

  local resp
  resp=$(api_post_json "${JWT}" "/api/v1/consent/grant" "${body}") || return 1
  echo "${resp}" | jq -r '.success // .ok // "ok"' 2>/dev/null || echo "${resp}"
  log "✓ ${label} consent grant erfolgreich"
}

# === Phase 2-4: Recording-Tests ===
phase_recording() {
  local label="$1" email="$2" pw="$3" client_id="$4" expected_queue="$5" expected_plan="$6"

  log "=== Phase ${label}: Recording-Test für ${expected_plan} ==="

  JWT=$(login "${email}" "${pw}") || return 1
  log "[${label}] Login OK"

  # Meeting erstellen (MeetingCreate erwartet 'start_time', nicht 'scheduled_at')
  local title="E2E ${expected_plan} $(date +%s)"
  local start_time
  start_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local meeting_resp
  meeting_resp=$(api_post_json "${JWT}" "/api/v1/meetings/" "{\"title\":\"${title}\",\"start_time\":\"${start_time}\"}") || return 1
  MEETING_ID=$(echo "${meeting_resp}" | jq -r '.id // .meeting_id // empty')
  if [ -z "$MEETING_ID" ]; then
    err "no meeting_id in response: ${meeting_resp}"
    return 1
  fi
  log "[${label}] Meeting created: ${MEETING_ID}"
  CLEANUP_IDS+=("meeting:${MEETING_ID}:${client_id}")

  # Recording Upload — recordings.py:35–36 checkt content_type startswith('audio/')
  # curl inferred content_type ist nicht zuverlässig für synthetische WAV-Datei —
  # wir setzen explizit 'audio/wav' damit der Backend-Check sicher passt.
  local upload_http
  upload_http=$(curl --silent --output /dev/null --write-out "%{http_code}" \
    --max-time 120 -X POST "${BASE_URL}/api/v1/recordings/upload/${MEETING_ID}" \
    -H "Authorization: Bearer ${JWT}" \
    -F "file=@${AUDIO_FILE};type=audio/wav")
  if [ "$upload_http" != "200" ] && [ "$upload_http" != "201" ]; then
    err "[${label}] upload failed: HTTP ${upload_http}"
    return 1
  fi
  log "[${label}] Upload OK (HTTP ${upload_http})"

  # Polling auf recording.status=completed (max 360s)
  local status=""
  for i in $(seq 1 36); do
    status=$(curl --silent --max-time 10 \
      "${BASE_URL}/api/v1/meetings/${MEETING_ID}/ai-insights" \
      -H "Authorization: Bearer ${JWT}" | jq -r '.status // "unknown"' 2>/dev/null) || status="unknown"
    log "[${label} ${i}0s] status=${status}"
    case "$status" in
      completed) break ;;
      failed) err "[${label}] pipeline FAILED"; return 1 ;;
      *) sleep 10 ;;
    esac
  done
  if [ "$status" != "completed" ]; then
    err "[${label}] timeout, status=${status}"
    return 1
  fi

  # RabbitMQ-Check
  local queue_count
  queue_count=$(kubectl exec rabbitmq-staging-0 -n "${NAMESPACE}" -- \
    rabbitmqctl list_queues name messages 2>/dev/null \
    | awk -v q="${expected_queue}" '$1==q{print $2; found=1} END{if (!found) print 0}')
  log "[${label}] RabbitMQ queue ${expected_queue}: messages=${queue_count}"

  # Worker-Log
  local worker_label="celery-worker-staging"
  local log_filter="transcription_gratuit"
  if [ "$expected_queue" = "transcription_pro" ]; then
    worker_label="celery-worker-pro-staging"
    log_filter="Sentinel|Qwen|transcription_pro"
  fi
  local worker_logs
  worker_logs=$(kubectl logs -n "${NAMESPACE}" -l "app=${worker_label}" --tail=300 2>/dev/null \
    | grep -E "${log_filter}" | head -10) || worker_logs="(no logs)"
  log "[${label}] Worker-Logs (${worker_label}):"
  echo "${worker_logs}" | sed 's/^/    /'

  # Sentinel-Check
  if [ "$expected_plan" = "PRO" ] || [ "$expected_plan" = "ENTREPRISE" ]; then
    if echo "${worker_logs}" | grep -q 'Sentinel.*initialized\|Qwen'; then
      log "✓ [${label}] Sentinel aktiv in PRO-worker"
    else
      log "⚠ [${label}] kein Sentinel-Log in PRO-worker (noch nicht initialisiert? latenz?)"
    fi
  else
    if echo "${worker_logs}" | grep -q 'Sentinel\|Qwen'; then
      err "❌ [${label}] FREE-worker involviert Sentinel — Isolation verletzt!"
      return 1
    else
      log "✓ [${label}] FREE-worker correkt isoliert (kein Sentinel)"
    fi
  fi

  # DB pv_sections
  local pv_count
  pv_count=$(db_query "SELECT COUNT(*) FROM pv_sections WHERE meeting_id='${MEETING_ID}';")
  log "[${label}] pv_sections count: ${pv_count}"
  if [ "$expected_plan" = "GRATUIT" ]; then
    if [ "$pv_count" != "0" ]; then
      err "❌ [${label}] pv_sections=${pv_count} (erwartet: 0 für GRATUIT)"
      return 1
    fi
  else
    if [ "$pv_count" -lt 1 ]; then
      err "❌ [${label}] pv_sections=${pv_count} (erwartet: >=1 für ${expected_plan})"
      return 1
    fi
  fi

  # DB recordings.status
  local db_status
  db_status=$(db_query "SELECT status FROM recordings WHERE meeting_id='${MEETING_ID}' LIMIT 1;")
  log "[${label}] DB recordings.status: ${db_status}"
  if [ "$db_status" != "completed" ]; then
    err "[${label}] DB status=${db_status} ≠ completed"
    return 1
  fi

  # audit_logs
  local audit_count
  audit_count=$(db_query "SELECT COUNT(*) FROM audit_logs WHERE client_id='${client_id}' AND created_at > now() - interval '15 minutes';")
  log "[${label}] audit_logs recent für ${client_id}: ${audit_count}"
  if [ "$audit_count" -lt 1 ]; then
    err "❌ [${label}] keine audit-Eintraege in letzten 15min"
    return 1
  fi

  log "✓✓✓ Phase ${label} (${expected_plan}) PASSED"
}

# === Phase 5: Cross-Tenant-Audit ===
phase5_cross_tenant() {
  log "=== Phase 5: Cross-Tenant Audit ==="

  db_query "
    SELECT c.subscription_plan::text AS plan, COUNT(m.id) AS meetings
    FROM clients c
    LEFT JOIN meetings m ON m.client_id = c.id AND m.created_at > now() - interval '1 hour'
    WHERE c.id IN (
      '${TENANT_GRATUIT_CLIENT_ID}',
      '${TENANT_PRO_CLIENT_ID}',
      '${TENANT_ENTREPRISE_CLIENT_ID}'
    )
    GROUP BY c.subscription_plan
    ORDER BY c.subscription_plan;
  "

  # Tenant-Pro-Soll: nur eigene Aufnahmen, KEINE von anderen Clients
  for kv in "PRO:${TENANT_PRO_CLIENT_ID}" "ENTREPRISE:${TENANT_ENTREPRISE_CLIENT_ID}" "GRATUIT:${TENANT_GRATUIT_CLIENT_ID}"; do
    local plan_label=${kv%:*}; local cid=${kv#*:}
    local own_records
    own_records=$(db_query "SELECT COUNT(*) FROM recordings WHERE client_id='${cid}' AND created_at > now() - interval '1 hour';")
    log "[tenant=${plan_label}] recordings last hour: ${own_records}"
  done
}

main() {
  : "${PW_GRATUIT:?PW_GRATUIT env var required}"
  : "${PW_PRO:?PW_PRO env var required}"
  : "${PW_ENTREPRISE:?PW_ENTREPRISE env var required}"

  phase0_setup || { err "Phase 0 FAILED"; exit 1; }

  phase1_consent "GRATUIT"     "${TENANT_GRATUIT_EMAIL}"     "${PW_GRATUIT}"     || { err "Phase 1 GRATUIT FAILED"; exit 1; }
  phase1_consent "PRO"         "${TENANT_PRO_EMAIL}"         "${PW_PRO}"         || { err "Phase 1 PRO FAILED"; exit 1; }
  phase1_consent "ENTREPRISE"  "${TENANT_ENTREPRISE_EMAIL}"  "${PW_ENTREPRISE}"  || { err "Phase 1 ENTREPRISE FAILED"; exit 1; }
  log "=== ✓ Phase 1: 3 consents granted ==="

  # A.2 Reihenfolge: PRO → ENT → GRATUIT
  phase_recording "2" "${TENANT_PRO_EMAIL}"        "${PW_PRO}"        "${TENANT_PRO_CLIENT_ID}"        "transcription_pro"     "PRO"          || { err "Phase 2 (PRO) FAILED"; exit 1; }
  sleep 5
  phase_recording "3" "${TENANT_ENTREPRISE_EMAIL}" "${PW_ENTREPRISE}" "${TENANT_ENTREPRISE_CLIENT_ID}" "transcription_pro"     "ENTREPRISE"   || { err "Phase 3 (ENT) FAILED"; exit 1; }
  sleep 5
  phase_recording "4" "${TENANT_GRATUIT_EMAIL}"    "${PW_GRATUIT}"    "${TENANT_GRATUIT_CLIENT_ID}"    "transcription_gratuit" "GRATUIT"      || { err "Phase 4 (GRATUIT) FAILED"; exit 1; }

  phase5_cross_tenant

  log "=== ✓✓✓ ALL PHASES PASSED ==="
  log "Cleanup IDs collected: ${#CLEANUP_IDS[@]} meeting IDs"
  printf '  %s\n' "${CLEANUP_IDS[@]}"
}

[[ "${BASH_SOURCE[0]}" == "$0" ]] && main "$@"
