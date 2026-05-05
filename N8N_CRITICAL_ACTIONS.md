# n8n Critical Actions - Quick Fix Guide
**Status**: 🔴 SYSTEM NOT PRODUCTION READY  
**Last Updated**: May 5, 2026

---

## 🚨 IMMEDIATE ACTIONS (Do These Now)

### ACTION 1: Fix .env Webhook URLs (5 minutes)
**File**: `.env`

Replace these lines (WRONG):
```env
N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/4/webhook/daily-reminders
N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/3/webhook/transcription-completed
```

With these (CORRECT):
```env
N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/daily-reminders
N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/transcription-completed
```

**Why**: Backend won't find the webhooks because paths include wrong workflow ID prefix.

---

### ACTION 2: Create SMTP Credential in n8n (10 minutes)

**Option A: Via UI (Recommended)**
1. Open http://localhost:5678 in browser
2. Go to **Settings** → **Credentials**
3. Click **Create New** → Select "Email (SMTP)"
4. Fill in:
   - Host: `smtp.gmail.com`
   - Port: `587`
   - User: `bkta3beispiel@gmail.com`
   - Password: `suvf wnpc kkjl bdor`
5. **Save** and note the credential ID (format: `xxxxxXXXXXxxxxx`)
6. Open each workflow that uses email (IDs: 2, 3, 4, 5, 6, 7)
   - Click the email node
   - Update "Credential" dropdown if needed
   - Save workflow (Ctrl+S)

**Option B: Via curl (Advanced)**
```bash
curl -X POST http://localhost:5678/api/v1/credentials \
  -H "Content-Type: application/json" \
  -H "X-N8N-API-KEY: $(your-api-key)" \
  -d '{
    "name": "SMTP account",
    "type": "emailSend",
    "data": {
      "host": "smtp.gmail.com",
      "port": 587,
      "user": "bkta3beispiel@gmail.com",
      "password": "suvf wnpc kkjl bdor",
      "secure": true
    }
  }'
```

**Why**: All email nodes will fail without this. Credential ID `eHaPFftWKgcTTXQc` doesn't exist.

---

### ACTION 3: Create Audio Uploaded Workflow (20 minutes)

Create file: `/n8n/workflows/audio-uploaded.json`

```json
{
  "id": "1",
  "name": "Audio Uploaded Automation",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "audio-uploaded",
        "options": {}
      },
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [100, 300]
    },
    {
      "parameters": {
        "url": "=http://meeting-automation-backend-1:8000/api/v1/transcription/start",
        "method": "POST",
        "sendHeaders": true,
        "headerParameters": {
          "parameters": [
            {
              "name": "X-Internal-API-Key",
              "value": "super-secret-automation-key-2026"
            }
          ]
        },
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "meeting_id",
              "value": "={{$json.body.meeting_id}}"
            },
            {
              "name": "audio_url",
              "value": "={{$json.body.audio_url}}"
            }
          ]
        },
        "options": {}
      },
      "name": "Start Transcription",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.1,
      "position": [350, 300]
    }
  ],
  "connections": {
    "Webhook": {
      "main": [[{"node": "Start Transcription", "type": "main", "index": 0}]]
    }
  },
  "active": true,
  "settings": {}
}
```

Then:
1. Open n8n UI: http://localhost:5678
2. **Settings** → **Import workflows**
3. Select the newly created `audio-uploaded.json`
4. Verify it's ACTIVE (green toggle, top right)
5. Verify webhook is registered (bottom of workflow editor)

**Why**: Backend will call `/webhook/audio-uploaded` when audio is uploaded. Without this workflow, you get 404 errors.

---

### ACTION 4: Register Missing Webhooks (10 minutes)

#### For Workflow 7 (Meeting Status Changed):
1. Open http://localhost:5678
2. Click workflow ID 7: "Meeting Status Changed Webhook"
3. Ensure **toggle is ON** (top right, should be GREEN)
4. **Save** (Ctrl+S)
5. **Verify**: Go to Settings → Webhooks, should see `meeting-status-changed` path

#### For Workflow 4 (Daily Reminders):
1. Same process: Open workflow 4
2. Check if there are webhook nodes (there shouldn't be - it's cron-triggered)
3. Just ensure it's saved and ACTIVE
4. The cron trigger should work automatically

**Why**: These workflows exist in the database but aren't registered as accessible webhooks. Without this, POST requests return 404.

---

## ⚠️ VERIFICATION (5 minutes)

### Test 1: Can n8n receive webhooks?
```bash
curl -X POST http://localhost:5678/webhook/meeting-created \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Meeting",
    "attendees": ["test@example.com"],
    "start_time": "2026-05-05T14:00:00Z"
  }'
```

**Expected**: `200 OK` (not 404)

### Test 2: Check database status
```bash
docker exec meeting-automation-postgres-1 psql -U meeting_user -d meeting_db \
  -c "SELECT id, name FROM workflow_entity WHERE active = true ORDER BY id;"
```

**Expected**: 7 rows (IDs 1-7, all active)

```bash
docker exec meeting-automation-postgres-1 psql -U meeting_user -d meeting_db \
  -c "SELECT COUNT(*) FROM webhook_entity;"
```

**Expected**: 7 rows (one for each webhook path)

### Test 3: Check SMTP credential exists
```bash
docker exec meeting-automation-postgres-1 psql -U meeting_user -d meeting_db \
  -c "SELECT COUNT(*) FROM credentials_entity WHERE type LIKE '%email%' OR type LIKE '%smtp%';"
```

**Expected**: 1 row with count > 0

---

## 📋 WORKFLOW STATUS CHECKLIST

After fixes, verify all 7 workflows:

| # | Workflow | Status | Notes |
|---|----------|--------|-------|
| 1 | Audio Uploaded | ⬜ | Create & import |
| 2 | Meeting Created | ⬜ | Fix webhook path, add SMTP credential |
| 3 | Transcription Completed | ⬜ | Fix webhook path, add SMTP credential |
| 4 | Daily Reminders | ⬜ | Register webhook, add WhatsApp credential |
| 5 | PV Validated | ⬜ | Add SMTP credential |
| 6 | User Invited | ⬜ | Add SMTP credential |
| 7 | Meeting Status Changed | ⬜ | Register webhook, add SMTP credential |

---

## 🔐 CREDENTIALS SETUP SUMMARY

After ACTION 2 and before testing, you should have:

| Credential | Type | Status | Location |
|-----------|------|--------|----------|
| SMTP account | Email (SMTP) | Should exist | Settings → Credentials |
| WhatsApp Token | HTTP Header Auth | Optional (Daily Reminders only) | Settings → Credentials |

All 7 workflows will fail at the email step without SMTP credential.

---

## 📊 EXPECTED WEBHOOK PATHS AFTER FIXES

```
/webhook/meeting-created              → Workflow 2
/webhook/transcription-completed      → Workflow 3
/webhook/daily-reminders              → Workflow 4 (Cron-triggered)
/webhook/pv-validated                 → Workflow 5
/webhook/user-invited                 → Workflow 6
/webhook/meeting-status-changed       → Workflow 7
/webhook/audio-uploaded               → Workflow 1
```

All should return `200 OK` when active.

---

## ⏱️ ESTIMATED TIME

| Action | Time | Difficulty |
|--------|------|-----------|
| Fix .env | 5 min | Easy |
| Create SMTP credential | 10 min | Easy |
| Create Audio Uploaded workflow | 20 min | Medium |
| Register missing webhooks | 10 min | Easy |
| Testing & verification | 5 min | Easy |
| **TOTAL** | **50 minutes** | **Easy-Medium** |

---

## 🆘 IF SOMETHING GOES WRONG

### Webhook still returns 404 after fixes?
1. Check .env was reloaded by backend: `docker compose restart backend`
2. Verify workflow is ACTIVE (green toggle) in n8n UI
3. Check webhook path: Click webhook node in workflow → "Production URL" tab
4. Check database: `SELECT * FROM webhook_entity WHERE "workflowId" = '2';`

### SMTP credential still not found?
1. Refresh n8n page (Ctrl+F5)
2. Re-open the credential in Settings
3. If credential ID changed, update workflow to use new ID
4. Test SMTP: Add a simple test email node, execute workflow

### Audio Uploaded workflow won't import?
1. Validate JSON syntax: `python -m json.tool audio-uploaded.json`
2. Check file permissions: `ls -la /n8n/workflows/audio-uploaded.json`
3. Check n8n logs: `docker compose logs n8n | grep -i error`

### Still stuck?
- Check full analysis report: `/home/opc/meeting-automation/N8N_ANALYSIS_REPORT_2026-05-05.md`
- Check n8n logs: `docker compose logs n8n --tail=100`
- Check backend logs: `docker compose logs backend | grep -i webhook`

---

**Last Updated**: May 5, 2026 20:58 UTC  
**Status**: AWAITING ACTION  
**Priority**: 🔴 CRITICAL
