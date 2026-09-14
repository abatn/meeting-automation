# Secret Audit — 2026-09-14

Scope: full tracked tree of this repository (`git grep` across 6 pattern classes) plus validation against the live prod/staging clusters and vendors. Follow-up to the credential redactions in `1058240e`, SOPS encryption in `0cfca4f5`/`efd76e5c`.

> This report intentionally contains **no secret values** — only locations and fingerprints.

## Executive summary

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | Seed-user passwords from public scripts are **live on PROD** (all 6 accounts incl. 3 superusers) | **CRITICAL** | 🔴 open |
| 2 | Mistral + Gladia API keys public **and live on staging** | **CRITICAL** | 🔴 open |
| 3 | Tracked JWT/credential files (admin token, n8n token, MinIO license, cookie jars) | MEDIUM | 🟡 expired, but should not be tracked |
| 4 | Personal-looking passwords in tracked scripts/migrations | MEDIUM | 🟡 not valid on prod (verified) |
| 5 | Dev-grade default creds in defaults/AGENTS.md/compose files | LOW | 🟢 informational |
| 6 | Untracked credential-adjacent files without .gitignore coverage | LOW | 🟢 local only (risk: future `git add .`) |

---

## 1. 🔴 CRITICAL — Public seed passwords are live on production

`backend/scripts/seed_users.py` and `backend/scripts/seed_plans.py` create users with a fixed, publicly readable password. Evidence chain:

- Prod DB (read-only check, `meeting_db`, verified 2026-09-14) contains exactly the 6 seeded accounts, all `ACTIVE`, created 2026-07-27:
  `admin@meeting.tn`, `tech@meeting.tn`, `batniniabdelkader@yahoo.com` (all superusers), plus `dg@meeting.tn`, `manager@meeting.tn`, `user@meeting.tn`.
- bcrypt verification against the prod `hashed_password` values: **all 6 accounts match the public seed password** (different hashes = different bcrypt salts, same password). This includes the owner's daily account (`dg@`, PRO tier) and 2 superusers.
- Anyone who reads this public repo can log into production today as admin.

**Required action:** rotate passwords for all 6 accounts + purge the password from the seed scripts (generate at runtime), and delete/rotate the seeded accounts that are not actually needed. Coordinate with the owner first (dg@ is the owner's login).

## 2. 🔴 CRITICAL — Live vendor keys public on staging

`infrastructure/kubernetes/staging/backend-secrets.yaml` was plaintext in git history (now SOPS-encrypted at HEAD, `0cfca4f5`), values remain in history:

- `MISTRAL_API_KEY` — confirmed **valid at vendor** (HTTP 200) and identical to the live staging cluster value.
- `GLADIA_API_KEY` — identical to live staging cluster value.
- `LIVEKIT_API_SECRET` (staging) — identical to live staging cluster value (both `backend-secrets-staging` and `livekit-secrets-staging`).

**Required action:** rotate Mistral + Gladia keys (vendor consoles), update staging secrets (now easy: `sops` edit + CI decrypt is in place). Prod values already rotated/differ.

## 3. 🟡 Tracked credential/JWT files (values expired, files tracked)

| File | Content | Validity |
|------|---------|----------|
| `admin_token.txt` | system_admin JWT (sub/client_id visible) | expired 2026-04-02 |
| `n8n_credential.txt` | n8n public-API JWT | expired 2026-05-01 |
| `minio_licenz.txt` | MinIO AIStor FREE license JWT — contains owner's **email** (PII) | n/a |
| `test-data/cookie-dg.txt`, `test-data/cookie-e2e.txt` | staging session cookies incl. sub/client_id/role | expired 2026-07-30 |

**Action:** remove from git (`git rm`) + gitignore; optionally BFG-purge. IDs reveal user/tenant UUIDs (useful for the multi-tenant attack surface).

## 4. 🟡 Personal-looking passwords in tracked files

- `backend/alembic/versions/v1w2x3y4z5a6_seed_gratuit_client_and_cleanup_usage.py` — bcrypt-seeded account with a personal-looking password in a comment.
- `backend/force_reset_pw.py` — hardcoded personal-looking password.

Verified **not** valid against prod hashes (bcrypt check: no match) — likely staging/older DB artifacts. Still: personal password patterns in a public repo are a targeted-attack gift. **Action:** replace with runtime-generated values; purge from history if owner confirms reuse elsewhere.

## 5. 🟢 Low — dev-grade defaults (accepted baseline)

- `backend/app/core/config.py:13,81` — `meeting_user:meeting_password`, `rabbit_user:rabbit_password` defaults.
- `AGENTS.md`, `docker-compose*.yml` (+ `.bak`/`.backup-*` variants) — same dev creds.
- `backend/tests/**` — test passwords in test fixtures: acceptable, but note that one fixture literal **is identical to the live prod seed password** (see finding 1; value intentionally not reproduced here — it is committed in `backend/scripts/seed_users.py` and `backend/scripts/seed_plans.py`). The fixture password should be changed too to avoid future confusion.
- Staging DB/Redis/MinIO passwords (now SOPS-encrypted at HEAD): weak but cluster-internal.

## 6. 🟢 Low — local files not gitignored

Untracked, not covered by `.gitignore` (one careless `git add .` away from publishing):

- `freebuff-chat-*.md` (agent session logs, 3.7 MB) — may embed secrets discussed in sessions
- `dump.rdb` (Redis dump — data, not code)
- `.agents/`, `backend/tests/performance/`, 3 `docs/*.md` investigation notes

**Action:** extend `.gitignore` (`freebuff-chat-*.md`, `dump.rdb`, `.loop.md` is already tracked but is a local-notes file — consider untracking it).

## Already fixed (this session)

| Commit | Fix |
|--------|-----|
| `1058240e` | Redacted 2× GitHub PATs, Supabase token, SMTP token, LiveKit secrets from `.loop.md` + `package.json` |
| `0cfca4f5` | SOPS-encrypted 8 staging secret manifests + CI decrypt step + `SOPS_AGE_KEY` |
| `efd76e5c` | SOPS-encrypted `traefik-tls-secret.yaml` (self-signed key material) + bootstrap-script handling |
| — | GitHub Secret Scanning, Push Protection, Validity Checks enabled (7 historical alerts, all checked: dead) |
| — | Prod LiveKit secret and prod DB password already differ from all leaked values (rotated previously) |

## Recommended order

1. **Today:** rotate the 6 prod user passwords (owner coordination for dg@) — finding 1.
2. **Today:** rotate Mistral + Gladia keys, update staging via sops — finding 2.
3. `git rm` the JWT/license/cookie files + extend `.gitignore` — findings 3/6.
4. Clean seed scripts (`seed_users.py`, `seed_plans.py`, migration comment, `force_reset_pw.py`) — finding 4 + prevents recurrence of finding 1.
5. Optional/destructive: history purge (BFG) — only after rotation, otherwise it buys nothing.
