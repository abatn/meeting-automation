# Frontend Patches

## `livekit-client.esm.mjs` — patched livekit-client@2.19.1 bundle

**What was patched:** `PCTransportManager.negotiate()` in the livekit-client ESM
bundle. See the header comment inside the file for the full rationale.

**Why:** livekit-server **v1.9.0** never echoes offer ids in answers
(`ToProtoSessionDescription` sets only `Type` + `Sdp`, so every answer carries
`id = 0`). livekit-client's `negotiate()` only clears its hardcoded **15s**
deadline when it receives `OfferAnswered(offerId > checkpoint)` (checkpoint = the
client's own last offer id, ≥ 1). With id-0 answers the deadline ALWAYS fires at
exactly 15s → `NegotiationError("negotiation timed out")` →
`fullReconnectOnNext` → `restartConnection()` → `sendLeave()` → the server logs
`CLIENT_REQUEST_LEAVE`. The app's `connectOptions.peerConnectionTimeout: 30000`
cannot help: it only sets the *engine's* timeout, never the
`PCTransportManager` property that guards the negotiation deadline.

**The fix:** the patched bundle resolves the pending negotiation when a
successfully-applied answer carries `offerId === 0` (the legacy "no-echo"
sentinel). This is safe because `OfferAnswered` is only emitted after
`setRemoteDescription()` succeeded, i.e. the negotiation genuinely completed.
Servers that DO echo ids (≥ v1.10.0) keep using the original `offerId > checkpoint`
path.

**How it is wired:** `frontend/vite.config.ts` → `resolve.alias`
`{ find: /^livekit-client$/, replacement: <patched file> }`. The regex anchors to
the exact package specifier so subpath imports like `livekit-client/e2ee-worker`
are not redirected. TypeScript types are unaffected (they still resolve from the
original package's `exports` map).

## Regenerating after a livekit-client upgrade

The patch is version-specific (byte-exact match against the bundle). After
upgrading `livekit-client` in `package.json`:

```bash
cd frontend
npm install                 # install the new version
python3 patches/patch-livekit-client.py
```

The script asserts the upstream `onAnswered` block matches exactly once and
**fails loudly** if the SDK code changed — in that case update the `OLD` block in
`patches/patch-livekit-client.py` to match the new bundle before regenerating.

## Verification

After `npm run build`, the built asset must contain the patched condition:

```bash
grep -o "negotiation timed out" dist/assets/*.js
python3 - <<'EOF'
import glob, re
for f in glob.glob('dist/assets/*.js'):
    src = open(f).read()
    m = re.search(r'negotiation timed out', src)
    if m:
        print(f, '->', src[m.start()-220:m.start()+80])
EOF
```

The snippet around `negotiation timed out` should contain `0===` (or
`offerId===0`-style) OR logic, proving the patched bundle was bundled.

## Long-term fix

The clean upstream fix is **upgrading livekit-server to ≥ v1.10.0**, which echoes
offer ids (`HandleOffer(offer, offerId, shouldPend)` + `GetAnswer() (answer,
answerId)` in `pkg/rtc/transportmanager.go`). Once the server is upgraded, this
client patch becomes a harmless no-op (id-0 answers no longer occur) and can be
removed.
