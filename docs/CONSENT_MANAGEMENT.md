# Consent Management — INPDP (Loi 2004-63) Compliance

## Legal Basis
- **Art. 47 Abs. 1**: Explicit consent required BEFORE data processing
- **Art. 47 Abs. 2**: Special consent for biometric data (voice profiles)
- **Art. 47 Abs. 3**: Information obligation for third-party data transfers
- **Art. 5 Nr. 2**: Biometric data = speaker embeddings (192-dim ONNX vectors)
- **Art. 5 Nr. 3**: Opinions = meeting transcripts
- **Art. 5 Nr. 4**: Business confidentiality = PVs (Process-Verbaux)

## Consent Types

| ID | Type | Required | Legal Basis |
|----|------|----------|-------------|
| C1 | audio_recording | YES | Art. 47 Abs. 1 |
| C2 | voice_profiling | NO (optional) | Art. 47 Abs. 2 + Art. 5 Nr. 2 |
| C3 | third_party_sharing | YES | Art. 47 Abs. 3 |
| C4 | transcript_storage | YES | Art. 47 Abs. 1 |

## Consent Texts (3 Languages)
See `frontend/src/i18n/locales/{en,fr-TN,ar-TN}.json` → `consent.*`

## Technical Implementation

### Backend
- **Model**: `consent_logs` table (UUID PK, FK to users/clients, consent_type enum, timestamps)
- **API**: 4 endpoints at `/api/v1/consent/`
  - `GET /status` — current user's consent status (4 booleans)
  - `POST /grant` — grant/update consent (captures IP + User-Agent)
  - `POST /withdraw` — withdraw consent (sets withdrawn_at, audit log)
  - `GET /history` — full audit trail ordered by timestamp
- **Registration**: C1+C3+C4 required to register. Registration rejected without them. In E2E_TEST mode, required consents are auto-granted.
- **Feature Gating**:
  - C1 (audio_recording) checked before `start_livekit_recording()` — HTTP 403 if missing
  - C2 (voice_profiling) checked before `auto_enrollment_service.enroll_or_update()` — skip if missing

### Frontend
- **ConsentDialog**: 4-step MUI Stepper with checkboxes
  - C1 (Audio Recording) = Required (must check to proceed)
  - C2 (Voice Profiling) = Optional (can skip)
  - C3 (Third-Party Sharing) = Required (information obligation)
  - C4 (Data Storage) = Required
- **Registration Flow**: ConsentDialog opens on form submit → user checks boxes → "I Confirm" enables → consents sent with registration data
- **Privacy Policy Page**: `/privacy` route renders all consent texts

### i18n
All consent texts available in 3 languages:
- EN (English)
- FR-TN (Français — Tunisie)
- AR-TN (العربية — تونس)

## Evidence Obligations (ISO 27001 / INPDP)
- **ConsentLog** captures: timestamp, IP address, user agent, consent version
- Full audit trail via `GET /api/v1/consent/history`
- Every consent change logged via `AuditService.log_action()` with action `CONSENT_GRANTED` or `CONSENT_WITHDRAWN`

## Withdrawal Procedure
- `POST /api/v1/consent/withdraw?consent_type=voice_profiling`
- Sets `withdrawn_at` timestamp, logs audit event
- Feature gates deactivate immediately (no auto-enrollment for withdrawn users)

## Feature Gating When Consent Refused
- **C1 refused**: Recording blocked with HTTP 403 "Audio recording consent required (INPDP Art. 47)"
- **C2 refused**: Auto-voice-enrollment skipped (speaker assigned manually instead)

## AVV (Auftragsverarbeitungsvertrag) Template
Required for third-party processors under Art. 47 Abs. 3:

| Third Party | Location | Processing | Legal Basis |
|------------|----------|------------|-------------|
| Gladia | France (EU) | Audio transcription, diarization | Art. 47 Abs. 3 |
| Mistral | France (EU) | AI processing, PV generation | Art. 47 Abs. 3 |
| Hetzner | Germany (EU) | Infrastructure, storage | Art. 47 Abs. 3 |
