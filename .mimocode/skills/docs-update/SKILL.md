# SKILL: Documentation Update

Systematic workflow for updating project documentation files in `docs/`.

**Description:** Read, analyze, and update documentation files to reflect current system state. Prevents outdated docs by following a structured verification process.

## When to Use

- User requests docs update (e.g., "aktualisiere die Doku")
- After major feature completion (e.g., pipeline optimization, new endpoints)
- Before releases or deployments
- When docs show outdated dates, test counts, or feature status

## Procedure

### Phase 1: Discovery

1. **Identify target files:**
   ```bash
   ls -la docs/*.md | grep -v PROTOCOL | head -20
   ```

2. **Check last modified dates:**
   ```bash
   stat --format="%y %n" docs/ARCHITECTURE.md docs/API.md docs/PROJECT_STATUS.md
   ```

3. **Read current state of each file:**
   - Note section headers and structure
   - Identify outdated content (dates, test counts, feature status)
   - Check for TODO/FIXME/placeholder content

### Phase 2: Verification

Before updating, verify current system state:

1. **Test count:**
   ```bash
   cd backend && pytest tests/ --co -q 2>/dev/null | tail -1
   ```

2. **Pipeline timing:**
   ```bash
   docker logs celery-worker 2>/dev/null | grep TIMING | tail -5
   ```

3. **Git log for recent changes:**
   ```bash
   git log --oneline -10
   ```

4. **Check running services:**
   ```bash
   docker-compose ps | grep -E "running|healthy"
   ```

### Phase 3: Update

For each file, follow this pattern:

#### ARCHITECTURE.md
- Update "PRODUCTION STATUS" date
- Add new services/modules (e.g., LiveKit SFU+Egress)
- Update Mermaid diagrams if architecture changed
- Add infrastructure details (RabbitMQ queues, Redis purposes, MinIO buckets)

#### API.md
- Add new endpoints (e.g., LiveKit token/webhook)
- Update response examples
- Complete truncated/placeholder sections
- Add authentication details for new endpoints

#### PROJECT_STATUS.md
- Update phase completion status
- Update test counts (e.g., 349/354 → current)
- Add new features (e.g., ONNX speaker ID, feedback resolution)
- Update "FINAL STATUS" date

### Phase 4: Validation

1. **Verify no broken links:**
   ```bash
   grep -n "docs/" docs/ARCHITECTURE.md | head -10
   ```

2. **Check file consistency:**
   - Test counts match across files
   - Feature status consistent
   - Dates are current

3. **Git diff to review changes:**
   ```bash
   git diff docs/
   ```

## Stopping Condition

- All target files updated with current state
- Test counts, dates, and feature status verified
- No broken internal references
- Git diff reviewed and clean

## Common Pitfalls

| Pitfall | Prevention |
|---------|------------|
| Claiming files read without actually reading | Always `Read` the file first, note line count |
| Outdated test counts | Verify with `pytest --co -q` before writing |
| Missing new endpoints | Check `app/api/v1/` for all route files |
| Inconsistent feature status | Cross-check across ARCHITECTURE, API, STATUS files |

## Notes

- User communicates in German — match language in docs where appropriate
- Never claim 100% completion without verification
- If unsure about a detail, mark as `[VERIFY]` rather than guessing
- Update docs in small, focused commits (one file per commit preferred)
