# Command: Frontend Check

Run frontend type-check and lint to catch errors before CI.

**Description:** Execute TypeScript type-check and optional lint on the frontend. Provides source-only error filtering for faster debugging.

## Usage

```
mimocode run frontend-check [--lint] [--fix] [--source-only]
```

**Arguments:**
- `--lint`: Also run ESLint (default: type-check only)
- `--fix`: Auto-fix lint errors where possible
- `--source-only`: Filter errors to only show `src/` files (ignore node_modules)

## Examples

```bash
# Type-check only (fastest)
mimocode run frontend-check

# Type-check + lint
mimocode run frontend-check --lint

# Source-only errors (for debugging)
mimocode run frontend-check --source-only

# Auto-fix lint errors
mimocode run frontend-check --lint --fix
```

## Procedure

### Step 1: Type-Check
```bash
cd /home/batnini/meeting-automation/frontend && \
npm run type-check 2>&1 | tail -20
```

### Step 2: Source-Only Filter (if --source-only)
```bash
cd /home/batnini/meeting-automation/frontend && \
npx tsc --noEmit 2>&1 | grep -E "^src/" | head -20
```

### Step 3: Lint (if --lint)
```bash
cd /home/batnini/meeting-automation/frontend && \
npm run lint 2>&1 | tail -20
```

### Step 4: Auto-Fix (if --fix)
```bash
cd /home/batnini/meeting-automation/frontend && \
npm run lint -- --fix 2>&1 | tail -10
```

## Stopping Condition

- Type-check passes (zero errors from `src/` files)
- Lint passes (if requested)
- OR errors are identified and documented

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `TS2345: id is string \| undefined` | Route params optional | Add `if (!id) return;` guard |
| `Cannot find name 'COLOR'` | Removed static constant | Use `buildColor(theme)` helper |
| `'theme' is of type 'unknown'` | Missing Theme import | Import `Theme` from `@mui/material/styles` |
| `Cannot find module './Component'` | Dead import | Remove unused import |

## Notes

- Frontend linting is **required in CI** (unlike backend)
- Run `npm ci` first if dependencies seem stale
- Vite dev server runs on port 3000 (not 5173)
- Always check `grep "^src/"` before claiming errors are pre-existing
