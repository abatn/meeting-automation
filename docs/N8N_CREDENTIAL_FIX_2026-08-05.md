# n8n Credential-ID Fix — Root Cause Analysis (2026-08-05)

## Problem

n8n Workflows auf Production schlugen fehl mit:
```
Credential with ID "VJcH9L41G0TRyOok" does not exist for type "smtp".
```

## Root Cause

### 1. n8n generiert zufällige Credential-IDs

Wenn ein Credential via UI oder API erstellt wird, generiert n8n eine **zufällige ID**:
- Staging: `RsSZHOzIodwgsuSc` (beim Setup generiert)
- Production: `AxoHUH4kCHlr0Zz4` (beim UI-Setup generiert)
- JSON im Repo: `VJcH9L41G0TRyOok` (ursprüngliche Erstellung, existiert nirgends)

### 2. `n8n import:workflow` übernimmt die JSON-ID

```
JSON im Repo: credentialId: "VJcH9L41G0TRyOok"
     ↓
n8n import:workflow kopiert ALLES including credentialId
     ↓
workflow_entity.nodes: "VJcH9L41G0TRyOok"
workflow_history.nodes: "VJcH9L41G0TRyOok"
     ↓
Aber credentials_entity hat: "AxoHUH4kCHlr0Zz4"
     ↓
Credential nicht gefunden → ERROR
```

### 3. n8n liest Nodes aus `workflow_history`, NICHT aus `workflow_entity`

Das ist der kritische Punkt:
- `workflow_entity` = Workflow-Definition (Versionierung)
- `workflow_history` = **Aktive Version** die n8n bei Start lädt

Wenn nur `workflow_entity` aktualisiert wird, bleibt n8n auf der alten Version.

## Fix (2026-08-05 durchgeführt)

### Schritt 1: workflow_entity aktualisieren
```sql
UPDATE workflow_entity
SET nodes = replace(nodes::text, 'VJcH9L41G0TRyOok', 'AxoHUH4kCHlr0Zz4')::jsonb
WHERE nodes::text LIKE '%VJcH9L41G0TRyOok%';
-- Ergebnis: UPDATE 6
```

### Schritt 2: workflow_history aktualisieren
```sql
UPDATE workflow_history
SET nodes = replace(nodes::text, 'VJcH9L41G0TRyOok', 'AxoHUH4kCHlr0Zz4')::jsonb
WHERE nodes::text LIKE '%VJcH9L41G0TRyOok%';
-- Ergebnis: UPDATE 6
```

### Schritt 3: n8n neustarten
```bash
kubectl rollout restart deployment/n8n -n meeting-automation
```

### Schritt 4: Test
```
POST /n8n/webhook/meeting-created → HTTP 200, Execution: success ✅
POST /n8n/webhook/user-invited → HTTP 200, Execution: success ✅
```

## CI/CD Auswirkung

Das `deploy-production.yml` Script muss BEIDE Tabellen aktualisieren:

```yaml
# Schritt: Update Workflow Credential References
- name: Update workflow_entity
  run: |
    kubectl exec ... -- psql -c "
      UPDATE workflow_entity
      SET nodes = replace(nodes::text, 'PLACEHOLDER_CRED_ID', '$NEW_CRED_ID')::jsonb
      WHERE nodes::text LIKE '%PLACEHOLDER_CRED_ID%';
    "

- name: Update workflow_history (KRITISCH!)
  run: |
    kubectl exec ... -- psql -c "
      UPDATE workflow_history
      SET nodes = replace(nodes::text, 'PLACEHOLDER_CRED_ID', '$NEW_CRED_ID')::jsonb
      WHERE nodes::text LIKE '%PLACEHOLDER_CRED_ID%';
    "

- name: Restart n8n
  run: kubectl rollout restart deployment/n8n -n meeting-automation
```

## Lessons Learned

| Lesson | Details |
|---|---|
| **Beide Tabellen updaten** | `workflow_entity` + `workflow_history` — n8n liest von `workflow_history` |
| **Credential-IDs sind umgebungs-spezifisch** | Jede Umgebung generiert eigene IDs |
| **JSON-Import übernimmt alte IDs** | `n8n import:workflow` kopiert inkl. credentialId |
| **Staging funktioniert zufällig** | weil die ID aus dem ersten Setup beibehalten wurde |
| **Production schlägt fehl** | weil neue ID + alte Referenz → Mismatch |

## Test-Payloads (flat, ohne body-Wrapper)

n8n's Webhook-Node packt den POST-Body automatisch unter `.body`:

```json
# meeting-created
POST /n8n/webhook/meeting-created
{
  "title": "Meeting Title",
  "attendees": ["email@test.com"],
  "start_time": "2026-08-06T10:00:00",
  "description": "...",
  "location": "Online",
  "meeting_link": "https://..."
}

# user-invited
POST /n8n/webhook/user-invited
{
  "email": "test@test.com",
  "full_name": "Test User",
  "company_name": "Company",
  "activation_link": "https://..."
}
```

## Aktueller Stand (nach Fix)

| Komponente | Staging | Production |
|---|---|---|
| Credential-ID in DB | `RsSZHOzIodwgsuSc` | `AxoHUH4kCHlr0Zz4` |
| Credential-ID in Nodes | `RsSZHOzIodwgsuSc` ✅ | `AxoHUH4kCHlr0Zz4` ✅ |
| Webhook meeting-created | ✅ success | ✅ success |
| Webhook user-invited | ✅ success | ✅ success |
