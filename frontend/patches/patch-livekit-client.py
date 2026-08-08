#!/usr/bin/env python3
"""
Regenerate frontend/patches/livekit-client.esm.mjs — a patched copy of the
livekit-client ESM bundle wired in via Vite alias (see ../vite.config.ts).

WHY THIS PATCH (root cause, PROVEN — see docs/LIVEKIT_15S_DISCONNECT_* and the
session analysis):
  livekit-server v1.9.0 never echoes offer ids in answers (ToProtoSessionDescription
  sets only Type + Sdp), so every answer arrives with id = 0. livekit-client's
  PCTransportManager.negotiate() only clears its 15s negotiation deadline when
  OfferAnswered(offerId > checkpoint) arrives (checkpoint = the client's own last
  offer id, >= 1). With id = 0 the deadline ALWAYS fires at exactly 15s ->
  NegotiationError("negotiation timed out") -> fullReconnectOnNext ->
  restartConnection() -> sendLeave() -> server logs CLIENT_REQUEST_LEAVE.

  The FIRST patch (offerId === 0 acceptance) resolved the negotiate() deadline
  only when an answer with id 0 was applied — but FOUR further 15s timeouts are
  hardcoded and NOT reached by the app's connectOptions (which only overrides the
  RTCEngine property, never the PCTransportManager field, never the literals):

    1. roomConnectOptionDefaults.peerConnectionTimeout: 15000  <- master default
       inherited by PCTransportManager.peerConnectionTimeout (negotiate deadline +
       ensureTransportConnected default) and RTCEngine.peerConnectionTimeout
       (waitForPCReconnected + ensureDataTransportConnected)
    2. roomConnectOptionDefaults.websocketTimeout: 15000       <- master default
    3. signalClient.join websocketTimeout: 15000 (x3, hardcoded) — initial join,
       ICE detect, region fallback
    4. LocalParticipant.waitForNextEngineRestart(timeoutMs = 15000) — runs right
       after a NegotiationError; on the slow ARM64 node an engine restart can
       exceed 15s -> rejects -> publish retry fails
    5. publishTrack timer (15000, hardcoded) — "publishing rejected as engine not
       connected within timeout"

  This script replaces ALL of the above with 60000ms (60s) so that no SDK-side
  timer can terminate a healthy connection at 15s on the constrained staging
  node. The id-0 acceptance is kept (correct for v1.9.0, harmless for >= 1.10.0).

  Intentionally NOT patched (not connection-drop timers):
    - CONNECTION_BACKOFF_MAX_MS = 15000  (max reconnect backoff delay)
    - responseTimeoutMs = 15000          (RPC request timeout)
    - STREAM_CHUNK_SIZE = 15000          (data chunk size, not a timeout)

Usage:
  python3 frontend/patches/patch-livekit-client.py

Run again after upgrading livekit-client in package.json — the script asserts the
upstream code still matches exactly and fails loudly otherwise.
"""

import json
import re
import sys
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent
SRC = FRONTEND / "node_modules" / "livekit-client" / "dist" / "livekit-client.esm.mjs"
PKG = FRONTEND / "node_modules" / "livekit-client" / "package.json"
OUT = FRONTEND / "patches" / "livekit-client.esm.mjs"

# ---------------------------------------------------------------------------
# Patch table: every patch must match its expected count, else fail loudly.
# ---------------------------------------------------------------------------
PATCHES = [
    {
        "name": "onAnswered id-0 negotiation fix",
        "old": """        const onAnswered = offerId => {
          if (offerId > checkpoint) {
            cleanup();
            resolve();
          }
        };""",
        "new": """        const onAnswered = offerId => {
          // PATCHED: livekit-server v1.9.0 never echoes offer ids, so answers
          // always carry offerId === 0. Without this, the 15s negotiation
          // deadline could never be cleared and fired at exactly 15s ->
          // NegotiationError -> CLIENT_REQUEST_LEAVE. Resolving on the legacy
          // id-0 sentinel is safe: OfferAnswered only fires after the answer
          // was applied successfully. Servers that echo ids (>= 1) keep the
          // original checkpoint path.
          if (offerId > checkpoint || offerId === 0) {
            cleanup();
            resolve();
          }
        };""",
        "count": 1,
    },
    {
        "name": "roomConnectOptionDefaults.peerConnectionTimeout 15000 -> 60000",
        "old": "peerConnectionTimeout: 15000,",
        "new": "peerConnectionTimeout: 60000, // PATCHED (was 15000: v1.9.0 id-0 + slow ARM64 node)",
        "count": 1,
    },
    {
        "name": "websocketTimeout defaults + signalClient.join literals 15000 -> 60000",
        "old": "websocketTimeout: 15000",
        "new": "websocketTimeout: 60000",
        "count": 4,  # 1x defaults + 3x signalClient.join (detect/retry/region)
    },
    {
        "name": "waitForNextEngineRestart default 15000 -> 60000",
        "old": "let timeoutMs = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : 15000;",
        "new": "let timeoutMs = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : 60000; // PATCHED (was 15000)",
        "count": 1,
    },
    {
        "name": "publishTrack engine-not-connected timer 15000 -> 60000",
        "old": """                reject(new PublishTrackError('publishing rejected as engine not connected within timeout', 408));
              }, 15000);""",
        "new": """                reject(new PublishTrackError('publishing rejected as engine not connected within timeout', 408));
              }, 60000); // PATCHED (was 15000)""",
        "count": 1,
    },
]

HEADER = """/*
 * PATCHED COPY of livekit-client@%(version)s (upstream: dist/livekit-client.esm.mjs)
 *
 * WHY: livekit-server v1.9.0 does not echo offer ids in answers (every answer
 * carries id = 0), so PCTransportManager.negotiate()'s 15s deadline could never
 * be cleared -> NegotiationError -> CLIENT_REQUEST_LEAVE at exactly 15s. The
 * first patch accepted offerId === 0 answers; this version additionally raises
 * EVERY 15s SDK timeout (master defaults, 3x signalClient.join websocketTimeout,
 * waitForNextEngineRestart, publishTrack timer) to 60000ms so no SDK timer can
 * drop a healthy connection at 15s on the constrained staging node.
 *
 * Regenerate after upgrading livekit-client:
 *   python3 frontend/patches/patch-livekit-client.py
 */
"""


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: {SRC} not found. Run `npm ci`/`npm install` first.", file=sys.stderr)
        return 1

    version = json.loads(PKG.read_text()).get("version", "unknown")
    src = SRC.read_text()

    # 1) Apply every patch, asserting exact match counts.
    for p in PATCHES:
        count = len(re.findall(re.escape(p["old"]), src))
        if count != p["count"]:
            print(
                f"ERROR: patch '{p['name']}' expected {p['count']} occurrence(s), "
                f"found {count} in livekit-client@{version}. The bundle changed — "
                f"update PATCHES in {__file__} before regenerating.",
                file=sys.stderr,
            )
            return 1
        src = src.replace(p["old"], p["new"])
        print(f"  ✓ {p['name']}: {count} replaced")

    # 2) Prepend a traceability header (module-level comment is safe).
    patched = HEADER % {"version": version} + "\n" + src

    # 3) Self-verification of the OUTPUT bundle.
    checks = {
        "offerId === 0 fix marker": ("offerId > checkpoint || offerId === 0", 1),
        "peerConnectionTimeout: 60000": ("peerConnectionTimeout: 60000", 1),
        "websocketTimeout: 60000 (4x: defaults + 3 joins)": ("websocketTimeout: 60000", 4),
        "waitForNextEngineRestart 60000": ("arguments[0] : 60000;", 1),
        "publishTrack 60000": ("}, 60000);", 1),
        "negotiation timed out sentinel": ("negotiation timed out", 1),
    }
    for label, (needle, expected) in checks.items():
        found = len(re.findall(re.escape(needle), patched))
        if found != expected:
            print(
                f"ERROR: self-verification failed — '{label}': expected {expected}, "
                f"found {found}. Fix PATCHES in {__file__}.",
                file=sys.stderr,
            )
            return 1

    leftovers = ["peerConnectionTimeout: 15000", "websocketTimeout: 15000",
                 "arguments[0] : 15000", "}, 15000);"]
    for needle in leftovers:
        found = len(re.findall(re.escape(needle), patched))
        if found != 0:
            print(
                f"ERROR: self-verification failed — leftover 15s pattern "
                f"'{needle}' found {found} time(s) in output. Fix PATCHES in {__file__}.",
                file=sys.stderr,
            )
            return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(patched)

    print(f"\nOK: wrote {OUT} ({len(patched)} bytes) for livekit-client@{version}")
    print("    all patches applied + self-verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
