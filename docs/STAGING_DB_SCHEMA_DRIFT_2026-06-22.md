# Staging DB Schema Drift: Root Cause Analysis + Fixes Applied

> **Date**: 2026-06-22 (updated)
> **Status**: FIXED ✅ — All missing columns added, pipeline working
> **Affected**: Kubernetes staging only (`meeting_db_staging`)
> **Docker Compose**: NOT affected (schema is correct)
> **Alembic version**: `m1n2o3p4q5r6`

---

## 1. Symptom

```
POST /api/v1/meetings/ → 500 Internal Server Error

asyncpg.exceptions.UndefinedColumnError:
  column clients.stripe_subscription_id does not exist
```

The `Client` SQLAlchemy model (line 61-62) references `stripe_subscription_id` and `stripe_customer_id`, but these columns do not exist in the staging DB.

---

## 2. Root Cause: Migration `8779f409105a` Was Stamped But Never Applied

### Migration chain

```
g1h2i3j4k5l6 (add_missing_indexes)
  ├── 8779f409105a (add_stripe_ids_to_clients)  ← BROKEN
  └── h2i3j4k5l6m (fix_meetingstatus_enum)
        └── j4k5l6m7n8o (merge_heads) ← STAGING STAMPED HERE
```

### What happened

1. Staging DB was created via `Base.metadata.create_all()` — tables created from SQLAlchemy models, but **without running Alembic migrations**
2. Alembic was then **stamped** at `j4k5l6m7n8o` (the merge head)
3. Stamping marks `8779f409105a` as "applied" without actually running it
4. The `clients` table never received `stripe_subscription_id` / `stripe_customer_id`

### Why `8779f409105a` cannot run

The migration is auto-generated and contains **side effects unrelated to its purpose**:

```python
def upgrade():
    # DROPS 13 indexes (these don't exist in staging DB!)
    op.drop_index('ix_action_assignments_action_id', ...)
    op.drop_index('ix_audit_logs_client_timestamp', ...)
    op.drop_index('ix_meetings_deleted_at', ...)
    op.drop_index('ix_meetings_start_time', ...)
    op.drop_index('ix_meetings_status', ...)
    # ... 8 more index drops
    
    # THE ACTUAL PURPOSE: Add 2 columns
    op.add_column('clients', sa.Column('stripe_subscription_id', ...))
    op.add_column('clients', sa.Column('stripe_customer_id', ...))
```

**Why the indexes don't exist**: The staging DB was created via `Base.metadata.create_all()`, which creates tables from models but does NOT create the performance indexes defined in migration `g1h2i3j4k5l6`. That migration's indexes were never applied to staging.

### Schema comparison

| Aspect | Docker DB (`meeting_db`) | Staging DB (`meeting_db_staging`) |
|--------|--------------------------|-----------------------------------|
| Alembic version | `8779f409105a` | `j4k5l6m7n8o` (includes `8779f409105a`) |
| `stripe_subscription_id` | ✅ Exists | ❌ Missing |
| `stripe_customer_id` | ✅ Exists | ❌ Missing |
| `ix_meetings_status` | ❌ Dropped by migration | ❌ Never created |
| `ix_action_assignments_action_id` | ❌ Dropped by migration | ❌ Never created |
| Total `ix_` indexes | 49 | 49 (different set) |

---

## 3. Fix Plan

### Step 1: Create a new safe migration (after `j4k5l6m7n8o`)

Created `backend/alembic/versions/k1l2m3n4o5p6_add_stripe_columns_safe.py`:
- Only adds `stripe_subscription_id` and `stripe_customer_id` (no index drops)
- Revision chain: `j4k5l6m7n8o` → `k1l2m3n4o5p6`

### Step 2: Fix meetingstatus enum mismatch

Created `backend/alembic/versions/l2m3n4o5p6q7_fix_meetingstatus_enum_uppercase.py`:
- DB had lowercase enum values (`planned`), Python model uses UPPERCASE (`PLANNED`)
- Uses `USING upper(status::text)::meetingstatus_v2` to convert in-place
- Revision chain: `k1l2m3n4o5p6` → `l2m3n4o5p6q7`

### Step 3: Apply and verify

```bash
# Applied via alembic upgrade head
alembic upgrade head
# → Running upgrade k1l2m3n4o5p6 -> l2m3n4o5p6q7

# Verified
\d clients → stripe_subscription_id, stripe_customer_id present
SELECT enumlabel FROM pg_enum → PLANNED, IN_PROGRESS, COMPLETED, CANCELLED
E2E smoke tests → 5/5 passed ✅
```

### Step 4: No setup script changes needed

The `setup-kubernetes-staging.sh` already:
1. Copies ALL migration files to the backend pod
2. Runs `alembic upgrade head` (not stamp)
3. The new safe migrations go after the stamped version, so they get applied automatically

---

## 4. Prevention

1. **Never use `alembic stamp head` on fresh databases** — always run `alembic upgrade head`
2. **Test migrations in isolation** — the auto-generated `8779f409105a` has dangerous side effects
3. **Add schema verification to setup scripts** — compare `Base.metadata` columns against actual DB columns
4. **Consider splitting `8779f409105a`** — the index drops should be a separate migration

---

## 5. Related Files

- `backend/alembic/versions/k1l2m3n4o5p6_add_stripe_columns_safe.py` — Safe migration adding stripe columns
- `backend/alembic/versions/l2m3n4o5p6q7_fix_meetingstatus_enum_uppercase.py` — Enum fix lowercase→UPPERCASE
- `backend/alembic/versions/8779f409105a_add_stripe_ids_to_clients.py` — Broken migration (drops unrelated indexes)
- `backend/alembic/versions/j4k5l6m7n8o_merge_heads.py` — Merge head (staging was stamped here)
- `backend/alembic/versions/g1h2i3j4k5l6_add_missing_indexes.py` — Creates indexes that `8779f409105a` drops
- `backend/app/models/client.py:61-62` — Model references stripe columns
- `backend/app/models/meeting.py:21-25` — Model defines UPPERCASE MeetingStatus enum
- `setup-kubernetes-staging.sh` — Already handles migrations correctly

---

## 6. Phase 2: Speakers + Recordings Columns (2026-06-22)

### Symptom 2

```
column recordings.access_policy does not exist
```

The `Recording` model references `access_policy`, `error_message`, `egress_id` — all missing.
The `Speaker` model references 7 columns that don't exist (`client_id`, `resolved_name`, `embedding`, etc.).

### Root Cause: Disconnected Migration Branches

The Alembic graph has **4 separate heads** — branches that were never merged:

| Head | Chain | What it adds |
|------|-------|-------------|
| `l2m3n4o5p6q7` | Main chain (27 migrations) | stripe columns, UPPERCASE enum |
| `08439ee30c73` | Branch from `c3fe9e232652` | CMS tables, access_policy, plan_code |
| `8779f409105a` | Orphan from `g1h2i3j4k5l6` | stripe columns (broken, drops indexes) |
| `d5e6f7a8b9c0` | Orphan from `abc123def456` | No-op constraints |

`alembic upgrade head` only follows the main chain. The branches from `c3fe9e232652` (which adds `access_policy`) and `8a1b2c3d4e5f` (which adds speaker profile columns) were never connected to the main chain.

### Missing Columns (confirmed via DB inspection)

**`speakers` table — 7 missing columns:**

| Column | Type | Default |
|--------|------|---------|
| `client_id` | VARCHAR (FK clients.id) | NULL |
| `resolved_name` | VARCHAR | NULL |
| `embedding` | JSON | NULL |
| `sample_count` | INTEGER | 0 |
| `mapping_confidence` | FLOAT | NULL |
| `mapping_method` | VARCHAR | NULL |
| `source` | VARCHAR | 'auto_enrolled' |

**`recordings` table — 3 missing columns:**

| Column | Type | Default |
|--------|------|---------|
| `access_policy` | VARCHAR | 'everyone' |
| `error_message` | VARCHAR | NULL |
| `egress_id` | VARCHAR | NULL |

### Fix Applied

Created `backend/alembic/versions/m1n2o3p4q5r6_add_missing_speakers_recordings_columns.py`:
- Uses `_column_exists()` guard for idempotent `ADD COLUMN IF NOT EXISTS` pattern
- Adds all 10 missing columns with proper types and defaults
- Down revision: `l2m3n4o5p6q7` (extends main chain)
- Applied: `alembic upgrade head` → `Running upgrade l2m3n4o5p6q7 -> m1n2o3p4q5r6`

### Setup Script Fix

Updated `setup-kubernetes-staging.sh` to copy migration files to **ALL** backend pods (not just the first one). With 2 replicas, `kubectl cp` only copies to one pod, but `kubectl exec` may run on the other.

### Verification

```sql
-- speakers: 11 columns (was 4)
-- recordings: 12 columns (was 9)
-- alembic_version: m1n2o3p4q5r6
```

---

## 7. Frontend Status Code Mismatch (2026-06-22)

### Symptom 3

```
POST /api/v1/meetings/ → 422 Unprocessable Entity
```

### Root Cause

Frontend sent `status: "planned"` (lowercase) but the UPPERCASE enum fix (`l2m3n4o5p6q7`) changed the backend to expect `"PLANNED"`.

### Fix Applied

Updated 4 frontend files:
- `MeetingPlanner.tsx:186` — `"planned"` → `"PLANNED"`
- `meetingsSlice.ts:7` — TypeScript type to UPPERCASE
- `DashboardManager.tsx:207,213` — Status comparisons to UPPERCASE
- `MeetingArchive.tsx:73` — Status comparison to UPPERCASE

---

## 8. Prevention

1. **Never use `alembic stamp head` on fresh databases** — always run `alembic upgrade head`
2. **Test migrations in isolation** — the auto-generated `8779f409105a` has dangerous side effects
3. **Add schema verification to setup scripts** — compare `Base.metadata` columns against actual DB columns
4. **Consider splitting `8779f409105a`** — the index drops should be a separate migration
5. **Copy migrations to ALL backend pods** — with multiple replicas, kubectl cp targets one pod
6. **Never use manual SQL to fix schema** — always create proper Alembic migrations
