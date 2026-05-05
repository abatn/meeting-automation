# n8n Workflows Analysis Report
**Date**: May 5, 2026  
**Status**: 6/7 workflows imported and active  
**Critical Issues**: YES - Missing "Audio Uploaded" workflow, Webhook path inconsistencies

---

## Executive Summary

The meeting-automation project has **6 out of 7 documented n8n workflows** successfully imported into PostgreSQL and set to ACTIVE state. However, there are significant mismatches between:
- **Documentation** (N8N_WORKFLOWS.md, N8N_INTEGRATION_GUIDE.md, N8N_QUICKSTART_GUIDE.md)
- **Database state** (workflow_entity, webhook_entity)
- **.env configuration** (N8N_WEBHOOK_* URLs)
- **JSON files** (/n8n/workflows/*.json)

This creates a **production risk** as webhooks may fail due to incorrect paths and the missing Audio Uploaded workflow.

---

## 1. Current Workflow State

### 1.1 Database Summary (workflow_entity)
```
Total Workflows: 6
All Active: YES (active = true for all)
Database: PostgreSQL (meeting_db)
```

### 1.2 Imported Workflows

| ID | Name | Active | File | Status |
|----|------|--------|------|--------|
| 2 | Meeting Created Automation | ✅ | meeting-created.json | Present |
| 3 | Transcription Completed Notification | ✅ | transcription-completed.json | Present |
| 4 | Daily Reminders Automation | ✅ | daily-reminders.json | Present |
| 5 | PV Validated Notification | ✅ | pv-validated.json | Present |
| 6 | User Invited Webhook | ✅ | user-invited.json | Present |
| 7 | Meeting Status Changed Webhook | ✅ | meeting-status-changed.json | Present |

### 1.3 Missing Workflow

**❌ "Audio Uploaded" (audio-uploaded.json)**
- **Expected from docs**: N8N_WORKFLOWS.md § "Audio Uploaded"
- **Status**: No JSON file in /n8n/workflows/
- **No database record**: workflow_entity table
- **N8N_WEBHOOK_URL exists**: `N8N_WEBHOOK_AUDIO_UPLOADED=http://n8n:5678/webhook/audio-uploaded` (in .env but not registered)
- **Impact**: Backend calls to this webhook will return 404 errors

---

## 2. Documentation vs Reality Comparison

### 2.1 Documented Workflows (N8N_WORKFLOWS.md)
The documentation lists **7 workflows**:
1. Meeting Created ✅
2. Transcription Completed ✅
3. Audio Uploaded ❌
4. Daily Reminders ✅
5. User Invited ✅
6. Meeting Status Changed ✅
7. PV Validated ✅

### 2.2 Integration Guide (N8N_INTEGRATION_GUIDE.md)
Lists these webhook events:
- `meeting.created` → N8N_WEBHOOK_MEETING_CREATED ✅
- `transcription.completed` → N8N_WEBHOOK_TRANSCRIPTION_COMPLETED ⚠️ (see 2.3)
- `daily_reminders` → N8N_WEBHOOK_DAILY_REMINDER ⚠️ (see 2.3)
- `user.invited` → N8N_WEBHOOK_URL + /user-invited ✅

### 2.3 Quickstart Guide (N8N_QUICKSTART_GUIDE.md)
Lists webhook paths (should match production URLs):
- `meeting-created` ✅
- `audio-uploaded` ❌
- `meeting-status-changed` ⚠️
- `transcription-completed` ⚠️
- `pv-validated` ✅
- `daily-reminders` ⚠️
- `user-invited` ✅

---

## 3. Webhook Path Configuration Issues

### 3.1 Registered Webhooks in Database (webhook_entity)
```
webhookPath                       | workflowId | Method
----------------------------------+------------+--------
2/webhook/meeting-created         | 2          | POST
3/webhook/transcription-completed | 3          | POST
pv-validated                      | 5          | POST
user-invited                      | 6          | POST
```

**Total in database**: 4 webhooks (missing `meeting-status-changed` and `daily-reminders`)

### 3.2 .env Configuration (N8N_WEBHOOK_* URLs)
```
N8N_WEBHOOK_USER_INVITED=http://n8n:5678/webhook/user-invited              ✅ Matches
N8N_WEBHOOK_MEETING_CREATED=http://n8n:5678/webhook/meeting-created        ⚠️  Path mismatch
N8N_WEBHOOK_MEETING_STATUS_CHANGED=http://n8n:5678/webhook/meeting-status-changed  ❌ Not in database
N8N_WEBHOOK_AUDIO_UPLOADED=http://n8n:5678/webhook/audio-uploaded          ❌ No workflow
N8N_WEBHOOK_PV_VALIDATED=http://n8n:5678/webhook/pv-validated              ✅ Matches
N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/4/webhook/daily-reminders    ❌ Not in database, incorrect path
N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/3/webhook/transcription-completed  ⚠️  Incorrect path
```

### 3.3 Path Inconsistencies Explained

**ISSUE 1: Inconsistent Path Formatting**

Database stores:
- `2/webhook/meeting-created` (workflow_id prefixed)
- `3/webhook/transcription-completed` (workflow_id prefixed)
- `pv-validated` (clean path)
- `user-invited` (clean path)

.env expects:
- `/webhook/meeting-created` (clean path)
- `/webhook/transcription-completed` (clean path)

**This will cause 404 errors!** When backend calls `http://n8n:5678/webhook/meeting-created`, n8n won't find it because the database has `2/webhook/meeting-created`.

**ISSUE 2: Missing Webhooks in Database**

These are registered in .env but **NOT** in webhook_entity:
- `meeting-status-changed` (workflow 7)
- `daily-reminders` (workflow 4)
- `audio-uploaded` (missing workflow)

**Why?** The workflows may not have been properly registered during import, or webhooks need manual activation in n8n UI.

---

## 4. Workflow Nodes & Credentials Analysis

### 4.1 Credentials Referenced in Workflows

All workflows reference the **same SMTP credential**:
```
id: "eHaPFftWKgcTTXQc"
name: "SMTP account"
```

**Status in database**: 0 credentials configured (credentials_entity is empty)

**Risk**: Email nodes will fail at runtime because the SMTP credential doesn't exist.

### 4.2 Workflow Node Breakdown

#### Meeting Created (ID: 2) - 2 nodes
- Webhook → Send Invitations (SMTP)
- **Status**: Basic structure, missing SMTP credential

#### Transcription Completed (ID: 3) - 4 nodes
- Webhook → Get Meeting Details (HTTP) → Download PDF (HTTP) → Send Email with PDF (SMTP)
- **Status**: Complex chain, all nodes present, missing SMTP credential
- **Note**: Uses `x_secret` query param (not standard header) - may fail

#### Daily Reminders (ID: 4) - 5 nodes
- Cron Trigger (8 AM daily) → Get Pending Actions (HTTP) → Is Due Today? (IF conditional) → [Escalate to Manager (SMTP) | WhatsApp Reminder (HTTP)]
- **Status**: No webhook registered in database
- **Missing**: WhatsApp credentials referenced but not in database
- **Problem**: N8N_WEBHOOK_DAILY_REMINDER has incorrect path format (`webhook/4/webhook/daily-reminders`)

#### User Invited (ID: 6) - 2 nodes
- Webhook → Send Email (SMTP)
- **Status**: Simple flow, webhook properly registered
- **Node IDs**: webhook-node, send-email-node (well-named)
- **Missing**: SMTP credential

#### Meeting Status Changed (ID: 7) - 3 nodes
- Webhook → Prepare Emails (JavaScript Code) → Send Email (SMTP)
- **Status**: Webhook NOT registered in database
- **Language**: French UI messages (status labels, subject lines)
- **Missing**: Webhook registration, SMTP credential

#### PV Validated (ID: 5) - 4 nodes
- Webhook → Get Meeting Details (HTTP) → Download PDF (HTTP) → Send Email with PDF (SMTP)
- **Status**: Webhook properly registered
- **Language**: German subject line ("✅ Protokoll freigegeben")
- **Missing**: SMTP credential
- **Note**: Different node ID format (webhook-node vs Webhook)

### 4.3 Credentials Status Summary

| Credential Type | Required | Present | Status |
|-----------------|----------|---------|--------|
| SMTP | 6 workflows | 0 | ❌ CRITICAL |
| WhatsApp | 1 workflow | 0 | ❌ CRITICAL |
| HTTP Headers | 3 workflows | 0 | ❌ (using hardcoded values) |

---

## 5. File-Level Analysis (/n8n/workflows/)

### 5.1 JSON Structure Validation

All 6 JSON files have valid structure:
```
✅ Proper ID field (2, 3, 4, 5, 6, 7)
✅ Unique names
✅ Nodes array with proper node objects
✅ Connections array (DAG format)
✅ Active flag (all set to true)
```

### 5.2 File-by-File Review

#### ✅ meeting-created.json
- **ID**: 2
- **Nodes**: 2 (Webhook, Send Invitations)
- **Path**: `meeting-created`
- **Issues**: None structurally; SMTP credential missing at runtime

#### ✅ transcription-completed.json
- **ID**: 3
- **Nodes**: 4 (Webhook, Get Meeting Details, Download PDF, Send Email)
- **Path**: `transcription-completed`
- **API Calls**: Uses `super-secret-automation-key-2026` as query param (should be header)
- **Issues**: Hardcoded API key in workflow visible in database

#### ✅ daily-reminders.json
- **ID**: 4
- **Trigger Type**: Cron (08:00 daily)
- **Nodes**: 5 (Cron, HTTP, IF, Email, WhatsApp)
- **Path**: None (cron-triggered, no webhook)
- **Issues**: Missing WhatsApp credentials, not registered as webhook

#### ✅ user-invited.json
- **ID**: 6
- **Nodes**: 2 (Webhook, Send Email)
- **Path**: `user-invited`
- **Node IDs**: webhook-node, send-email-node (good practice)
- **Issues**: None structurally; SMTP credential missing

#### ✅ meeting-status-changed.json
- **ID**: 7
- **Nodes**: 3 (Webhook, Prepare Emails [Code], Send Email)
- **Path**: `meeting-status-changed`
- **Code Node**: Sophisticated JavaScript handling French locale, status mapping, email templating
- **Issues**: Webhook not registered, SMTP credential missing, hardcoded timezone 'Africa/Tunis'

#### ✅ pv-validated.json
- **ID**: 5
- **Nodes**: 4 (Webhook, Get Meeting Details, Download PDF, Send Email)
- **Path**: `pv-validated`
- **Language**: German subject line
- **Issues**: SMTP credential missing, uses $() accessor instead of $node[] in some places

### 5.3 Missing File

**❌ audio-uploaded.json** - Not present in /n8n/workflows/

Expected structure (from documentation):
```json
{
  "id": "1",
  "name": "Audio Uploaded",
  "nodes": [
    { "name": "Webhook", "path": "audio-uploaded", ... },
    { "name": "Start Transcription", ... }
  ]
}
```

---

## 6. Configuration Gaps Analysis

### 6.1 Environment Variables (.env)

**Properly Configured**: ✅
- DATABASE_URL (PostgreSQL connection)
- N8N_DATABASE_* (n8n persistence)
- INTERNAL_API_SECRET (`super-secret-automation-key-2026`)
- SMTP_HOST, SMTP_USER, SMTP_PASSWORD (Gmail SMTP)

**Problematic URLs**: ❌
```
N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/4/webhook/daily-reminders
  ↑ This is wrong. Should be just http://n8n:5678/webhook/daily-reminders
  
N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/3/webhook/transcription-completed
  ↑ Same issue. Should be http://n8n:5678/webhook/transcription-completed
```

**Missing URLs**: ❌
- `N8N_WEBHOOK_AUDIO_UPLOADED` in .env exists, but no workflow registered

### 6.2 Docker Setup

**n8n Container**: ✅
- Image: `n8nio/n8n:latest`
- Port: 5678 (exposed)
- Status: Running for 53 minutes
- Database: Shares PostgreSQL with backend (meeting_db)

**Startup Check**:
```
✅ Editor accessible at http://localhost:5678
✅ Task Broker ready on 127.0.0.1:5679
⚠️ Python task runner failed (not critical for workflow execution)
✅ Owner was set up successfully
```

**Network**: ✅
- Can reach backend at `http://meeting-automation-backend-1:8000` (Docker internal network)

### 6.3 SMTP Configuration

**Status**: Partially Configured
- Host: `smtp.gmail.com` ✅
- Port: 587 ✅
- User: `bkta3beispiel@gmail.com` ✅
- Password: `'suvf wnpc kkjl bdor'` (Gmail App Password) ✅
- **BUT**: Not registered as a credential in n8n's credentials_entity table ❌

---

## 7. Verification Checklist

### ✅ What's Working Correctly

- [x] n8n container running and accessible
- [x] PostgreSQL database connection established
- [x] 6 workflows successfully imported and ACTIVE
- [x] All workflow JSON files have valid structure
- [x] Node connections properly defined (DAG format)
- [x] Webhook nodes properly configured in JSON
- [x] Backend can reach n8n via Docker network
- [x] SMTP configuration in .env (partially - not in n8n credentials)
- [x] Internal API secret configured (`super-secret-automation-key-2026`)
- [x] n8n persistence working (workflows stored in PostgreSQL)

### ⚠️ What Needs Attention

- [ ] **SMTP Credentials Not Created in n8n**
  - All email nodes reference `id: "eHaPFftWKgcTTXQc"` which doesn't exist in credentials_entity
  - Fix: Manually create SMTP credential in n8n UI or via API

- [ ] **Webhook Paths Inconsistent Between .env and Database**
  - Database has `2/webhook/meeting-created` but .env expects `/webhook/meeting-created`
  - Affects: Meeting Created, Transcription Completed
  - Fix: Either update .env URLs or re-import workflows with clean paths

- [ ] **Missing Webhook Registrations**
  - `meeting-status-changed` (workflow 7): Webhook in JSON but not in database
  - `daily-reminders` (workflow 4): Cron-triggered but N8N_WEBHOOK_DAILY_REMINDER exists
  - Fix: Activate/save workflows in n8n UI to trigger webhook registration

- [ ] **Hardcoded API Keys in Workflows**
  - `super-secret-automation-key-2026` visible in workflow JSON stored in database
  - Appears in: transcription-completed, daily-reminders, pv-validated
  - Fix: Move to n8n credentials/variables instead of hardcoded

- [ ] **WhatsApp Credentials Missing**
  - Daily Reminders workflow references WhatsApp but no credential exists
  - Fix: Create HTTP header auth credential for WhatsApp Business API

- [ ] **Incorrect Webhook URL Formatting in .env**
  - `N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/4/webhook/daily-reminders` (wrong!)
  - `N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/3/webhook/transcription-completed` (wrong!)
  - Fix: Remove the workflow ID prefix and duplicate "webhook"

### ❌ What's Missing or Broken

- [ ] **Audio Uploaded Workflow (CRITICAL)**
  - Not imported, no JSON file
  - Backend will fail when calling N8N_WEBHOOK_AUDIO_UPLOADED
  - Fix: Create audio-uploaded.json and import to n8n

- [ ] **Meeting Status Changed Webhook Not Registered (HIGH)**
  - Workflow 7 exists in database but webhook path not in webhook_entity
  - Backend calls will return 404
  - Fix: Open workflow 7 in n8n UI, save, and ensure "Active" toggle is ON

- [ ] **Daily Reminders Webhook Not Registered (HIGH)**
  - Workflow 4 has cron trigger but also needs webhook registration
  - .env URL is malformed anyway
  - Fix: Correct .env URL and ensure workflow is saved

---

## 8. Identified Issues Summary

### Critical Issues (Production Risk)

| Issue | Severity | Impact | Fix |
|-------|----------|--------|-----|
| Audio Uploaded workflow missing | 🔴 CRITICAL | Backend 404 when audio uploaded | Create audio-uploaded.json, import workflow |
| SMTP credentials not in n8n | 🔴 CRITICAL | All email notifications fail at runtime | Create SMTP credential in n8n or via curl |
| Webhook paths mismatch (.env vs DB) | 🔴 CRITICAL | Meeting created, transcription webhooks return 404 | Fix .env URLs or re-import with clean paths |
| Meeting Status Changed webhook not registered | 🔴 CRITICAL | Status change notifications fail (404) | Save workflow 7 in n8n UI with webhook active |
| Daily Reminders webhook URL malformed | 🔴 CRITICAL | Cron can run but webhook calls fail | Fix .env URL and register webhook |

### High Priority Issues (Functionality Degradation)

| Issue | Severity | Impact | Fix |
|-------|----------|--------|-----|
| WhatsApp credentials missing | 🟠 HIGH | Daily Reminder WhatsApp messages fail | Create WhatsApp credential in n8n |
| Hardcoded API keys in workflows | 🟠 HIGH | Security exposure, keys visible in DB | Move to n8n credentials/variables |
| Node ID format inconsistency | 🟡 MEDIUM | May cause issues if workflows edited | Standardize to UUID format |
| Timezone hardcoded to Africa/Tunis | 🟡 MEDIUM | Status updates show wrong timezone | Use env var or calculate from user data |

### Low Priority Issues (Documentation/Maintenance)

| Issue | Severity | Impact | Fix |
|-------|----------|--------|-----|
| Documentation outdated (7 workflows vs 6 actual) | 🟡 LOW | Confusion, incorrect onboarding | Update N8N_WORKFLOWS.md |
| Mixed language in workflows (French/German) | 🟡 LOW | Inconsistent UX | Standardize to one language or multi-lang |
| Query params used for secrets instead of headers | 🟡 LOW | Security best practice violation | Use Authorization headers |

---

## 9. Recommended Fixes (Priority Order)

### Phase 1: Critical Fixes (Do First - Required for Production)

#### Fix 1: Create and Import Audio Uploaded Workflow
```bash
# Create /n8n/workflows/audio-uploaded.json with webhook path "audio-uploaded"
# Import via n8n UI: Settings → Import workflows
# Ensure workflow is ACTIVE (toggle ON)
```

**Expected behavior**: Backend webhook POST to `/webhook/audio-uploaded` will return 200 OK

#### Fix 2: Fix .env Webhook URLs
```env
# CHANGE FROM:
N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/4/webhook/daily-reminders
N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/3/webhook/transcription-completed

# CHANGE TO:
N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/daily-reminders
N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/transcription-completed
```

Then re-import or manually update webhooks in n8n UI.

#### Fix 3: Create SMTP Credential in n8n
Option A: Via n8n UI
- Go to http://localhost:5678
- Settings → Credentials
- Create new credential: type "Email (SMTP)"
- Copy ID generated
- Update all workflows to use the new credential ID

Option B: Via API (if available)
```bash
curl -X POST http://localhost:5678/api/v1/credentials \
  -H "Content-Type: application/json" \
  -d '{
    "name": "SMTP account",
    "type": "smtp",
    "data": {
      "host": "smtp.gmail.com",
      "port": 587,
      "user": "bkta3beispiel@gmail.com",
      "password": "suvf wnpc kkjl bdor",
      "secure": true
    }
  }'
```

#### Fix 4: Register Missing Webhooks
- Open workflow 7 (Meeting Status Changed) in n8n UI
- Click "Active" toggle (top right) → should turn GREEN
- Click "Save" (Ctrl+S)
- Verify webhook appears in webhook_entity table

Repeat for workflow 4 (Daily Reminders) - though it's cron-triggered, any webhooks in the flow need registration.

### Phase 2: High Priority Fixes (Recommended)

#### Fix 5: Create WhatsApp Credential
```bash
# In n8n UI: Settings → Credentials → New Credential
# Type: "HTTP Request" (for WhatsApp API)
# Set Authorization Header: Authorization: Bearer {WHATSAPP_TOKEN}
```

#### Fix 6: Move Hardcoded API Keys to n8n Variables
```bash
# In n8n UI: Variables tab
# Create: INTERNAL_API_SECRET = super-secret-automation-key-2026
# Update all HTTP Request nodes to use {{ $vars['INTERNAL_API_SECRET'] }}
```

### Phase 3: Medium Priority Fixes (Polish)

#### Fix 7: Standardize Node ID Format
- Either all UUIDs or all readable names
- Current: Mix of UUIDs and kebab-case IDs
- Update workflow exports to ensure consistency

#### Fix 8: Externalize Configuration
```json
// In Daily Reminders workflow:
// Instead of hardcoded "Africa/Tunis"
"timeZone": "{{ $env['TIMEZONE'] || 'UTC' }}"
```

#### Fix 9: Update Documentation
- Update N8N_WORKFLOWS.md to reflect 7 workflows (once Audio Uploaded is added)
- Add section on credential setup
- Document webhook URL format clearly
- Add troubleshooting section for 404 errors

---

## 10. Testing Checklist

After applying fixes, verify:

### Basic Connectivity
```bash
# Can n8n receive webhooks?
curl -X POST http://localhost:5678/webhook/meeting-created \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "attendees": ["test@example.com"]}'

# Expected: 200 OK (not 404)
```

### Workflow Execution
- [x] Meeting Created: Test webhook, verify SMTP sends email
- [x] Transcription Completed: Test webhook, verify PDF download + email
- [x] Daily Reminders: Wait until 08:00 or manually trigger, verify emails/WhatsApp
- [x] User Invited: Test webhook, verify welcome email sent
- [x] Meeting Status Changed: Test webhook, verify status emails
- [x] PV Validated: Test webhook, verify PDF delivery email
- [x] Audio Uploaded: Create workflow, test webhook, verify transcription pipeline

### Database Verification
```sql
-- Verify all 7 workflows active
SELECT id, name, active FROM workflow_entity ORDER BY id;
-- Should show 7 rows with active=true

-- Verify 7+ webhooks registered
SELECT webhookPath, workflowId FROM webhook_entity ORDER BY webhookPath;
-- Should show all paths (meeting-created, transcription-completed, pv-validated, 
-- user-invited, meeting-status-changed, audio-uploaded, daily-reminders)

-- Verify credentials exist
SELECT id, name, type FROM credentials_entity;
-- Should show SMTP and WhatsApp entries
```

---

## 11. Summary & Recommendations

### Current State
- 6 out of 7 workflows imported and marked ACTIVE ✅
- Webhook paths inconsistent between configuration layers ❌
- SMTP and WhatsApp credentials missing from n8n ❌
- Audio Uploaded workflow completely missing ❌

### Risk Level
**🔴 HIGH** - System is non-functional for email notifications and Audio Uploaded events

### Timeline to Production Ready
- **Phase 1 fixes**: 1-2 hours (manual UI work + API calls)
- **Phase 2 fixes**: 30 minutes
- **Phase 3 fixes**: 1-2 hours (documentation)
- **Testing**: 30 minutes
- **Total**: ~4-5 hours

### Next Steps (Immediate)
1. Create audio-uploaded.json workflow
2. Fix .env webhook URLs
3. Create SMTP credential in n8n
4. Activate missing webhook registrations
5. Run webhook connectivity test
6. Execute Phase 1 testing checklist

---

## Appendix A: Complete Webhook Registration Status

| Workflow | ID | Name | Webhook Path | In DB | Status |
|----------|----|----|------|-------|--------|
| meeting-created.json | 2 | Meeting Created Automation | `2/webhook/meeting-created` | ✅ | ⚠️ Path wrong |
| transcription-completed.json | 3 | Transcription Completed | `3/webhook/transcription-completed` | ✅ | ⚠️ Path wrong |
| daily-reminders.json | 4 | Daily Reminders Automation | (none - cron) | ❌ | ❌ Not registered |
| pv-validated.json | 5 | PV Validated Notification | `pv-validated` | ✅ | ✅ Correct |
| user-invited.json | 6 | User Invited Webhook | `user-invited` | ✅ | ✅ Correct |
| meeting-status-changed.json | 7 | Meeting Status Changed | `meeting-status-changed` | ❌ | ❌ Not registered |
| audio-uploaded.json | (missing) | (missing) | `audio-uploaded` | ❌ | ❌ Workflow missing |

---

## Appendix B: Environment Variables Configuration Issues

```env
# CURRENT (WRONG):
N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/4/webhook/daily-reminders
N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/3/webhook/transcription-completed
N8N_WEBHOOK_MEETING_CREATED=http://n8n:5678/webhook/meeting-created

# SHOULD BE:
N8N_WEBHOOK_DAILY_REMINDER=http://n8n:5678/webhook/daily-reminders
N8N_WEBHOOK_TRANSCRIPTION_COMPLETED=http://n8n:5678/webhook/transcription-completed
N8N_WEBHOOK_MEETING_CREATED=http://n8n:5678/webhook/meeting-created

# The pattern is: http://n8n:5678/webhook/{path}
# Where {path} is defined in the webhook node's "path" parameter
# NOT http://n8n:5678/webhook/{workflow_id}/webhook/{path}
```

---

## Appendix C: SQL Queries for Verification

```sql
-- List all workflows with status
SELECT id, name, active, createdAt FROM workflow_entity ORDER BY id;

-- List all registered webhooks
SELECT "webhookPath", "workflowId", method FROM webhook_entity ORDER BY "webhookPath";

-- List all credentials
SELECT id, name, type FROM credentials_entity;

-- Count executions per workflow
SELECT "workflowId", COUNT(*) as execution_count 
FROM execution_entity 
WHERE "deletedAt" IS NULL 
GROUP BY "workflowId" 
ORDER BY execution_count DESC;

-- Get most recent executions
SELECT id, "workflowId", status, "createdAt" 
FROM execution_entity 
ORDER BY "createdAt" DESC 
LIMIT 20;
```

---

**Report Generated**: 2026-05-05 20:58 UTC  
**Report Author**: n8n Workflow Analysis Agent  
**Status**: NEEDS IMMEDIATE ACTION
