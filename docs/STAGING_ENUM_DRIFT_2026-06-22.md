# Staging Enum Drift: facturestatus + suggestionstatus UPPERCASE Fix

> **Date**: 2026-06-22
> **Status**: Migration created, pending apply
> **Affected**: Kubernetes staging only (`meeting_db_staging`)
> **Alembic version**: `m1n2o3p4q5r6` → `n2o3p4q5r6s7`

---

## 1. Symptom

Backend logs during dashboard/API calls:

```
invalid input value for enum suggestionstatus: "ACCEPTED"
```

`/api/v1/actions/statistics/recurring?lang=en` returned **500 Internal Server Error**.

Same root cause pattern as `meetingstatus` (fixed in `l2m3n4o5p6q7`):
DB enums created with **lowercase** values, Python models define **UPPERCASE**.

---

## 2. Investigation

### Evidence

| Source | Finding |
|--------|---------|
| `backend/app/models/billing.py` | `FactureStatus.PAID = "PAID"` (UPPERCASE) |
| `backend/app/models/action.py` | `SuggestionStatus.ACCEPTED = "ACCEPTED"` (UPPERCASE) |
| PostgreSQL `pg_enum` | `facturestatus`: `paid`, `pending`, `failed`, `cancelled` (lowercase) |
| PostgreSQL `pg_enum` | `suggestionstatus`: `suggested`, `accepted`, `rejected` (lowercase) |
| Backend error log | `invalid input value for enum suggestionstatus: "ACCEPTED"` |

### Root Cause

The staging DB was created via `Base.metadata.create_all()` which uses the Python model's enum values. However, at some point the enum types were recreated with lowercase values — likely during the `h2i3j4k5l6m` migration which dropped and recreated `meetingstatus` with lowercase, and this pattern was applied to other enums too.

The `l2m3n4o5p6q7` migration fixed `meetingstatus` but missed `facturestatus` and `suggestionstatus`.

### Affected Enums

| Enum | Table | DB Values (lowercase) | Code Values (UPPERCASE) |
|------|-------|----------------------|------------------------|
| `facturestatus` | `factures` | `paid, pending, failed, cancelled` | `PAID, PENDING, FAILED, CANCELLED` |
| `suggestionstatus` | `action_suggestions` | `suggested, accepted, rejected` | `SUGGESTED, ACCEPTED, REJECTED` |

---

## 3. Plan

### Approach: Alembic Migration (not manual SQL)

Created `backend/alembic/versions/n2o3p4q5r6s7_fix_facturestatus_suggestionstatus_enum_uppercase.py`:

1. Create new enum type with UPPERCASE values (`facturestatus_v2`, `suggestionstatus_v2`)
2. Convert column using `USING upper(status::text)::new_enum_type` (safe one-step conversion)
3. Drop old enum type, rename new to original name
4. Downgrade reverses to lowercase

### Migration Chain

```
m1n2o3p4q5r6 (add_missing_speakers_recordings_columns)
  └── n2o3p4q5r6s7 (fix facturestatus + suggestionstatus UPPERCASE) ← NEW
```

---

## 4. Implementation

### Step 1: Apply migration to staging DB

```bash
kubectl exec -n meeting-automation-staging <backend-pod> -- \
  alembic upgrade head
```

### Step 2: Verify enum values

```sql
SELECT enumlabel FROM pg_enum WHERE enumtypid = (
  SELECT oid FROM pg_type WHERE typname = 'facturestatus'
) ORDER BY enumsortorder;
-- Expected: CANCELLED, FAILED, PAID, PENDING

SELECT enumlabel FROM pg_enum WHERE enumtypid = (
  SELECT oid FROM pg_type WHERE typname = 'suggestionstatus'
) ORDER BY enumsortorder;
-- Expected: ACCEPTED, REJECTED, SUGGESTED
```

### Step 3: Restart backend pods

```bash
kubectl rollout restart deployment/backend -n meeting-automation-staging
```

### Step 4: Verify API endpoints

- `GET /api/v1/actions/statistics/recurring?lang=en` → 200 (was 500)
- Dashboard loads without errors

---

## 5. Prevention

1. **Always use UPPERCASE enum values** in PostgreSQL (Python convention)
2. **Test enum conversions** before deploying — check `pg_enum` vs model values
3. **Setup scripts should verify enum values** — add to schema verification step
4. **Never use manual SQL** to fix enum drift — create proper Alembic migration

---

## 6. Related Files

- `backend/alembic/versions/n2o3p4q5r6s7_fix_facturestatus_suggestionstatus_enum_uppercase.py` — New migration
- `backend/alembic/versions/l2m3n4o5p6q7_fix_meetingstatus_enum_uppercase.py` — Previous enum fix (meetingstatus)
- `backend/app/models/billing.py` — `FactureStatus` enum definition
- `backend/app/models/action.py` — `SuggestionStatus` enum definition
- `docs/STAGING_DB_SCHEMA_DRIFT_2026-06-22.md` — Previous schema drift documentation
