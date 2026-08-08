#!/usr/bin/env node
/**
 * Prebuild guard: fail loudly if the committed patched livekit-client bundle
 * (patches/livekit-client.esm.mjs) drifts from the SDK installed in
 * node_modules, or if the patch marker is missing.
 *
 * The patched copy is static and committed, so a `livekit-client` version bump
 * in package.json followed by `npm ci` would otherwise silently keep bundling
 * the stale 2.19.1 copy via the Vite alias. This script makes that failure
 * loud instead. Pure Node (no Python dependency) so it runs in the Docker/CI
 * build image.
 *
 * Wire-up: "prebuild": "node patches/check-livekit-patch.mjs" in package.json.
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const patchedPath = join(root, 'patches', 'livekit-client.esm.mjs');
const pkgPath = join(root, 'node_modules', 'livekit-client', 'package.json');

let installedVersion;
try {
  installedVersion = JSON.parse(readFileSync(pkgPath, 'utf8')).version;
} catch {
  console.error(
    '❌ livekit-client not found in node_modules. Run `npm ci`/`npm install` first.',
  );
  process.exit(1);
}

let patched;
try {
  patched = readFileSync(patchedPath, 'utf8');
} catch {
  console.error(
    `❌ Patched bundle missing: ${patchedPath}\n` +
      '   Regenerate it: python3 patches/patch-livekit-client.py',
  );
  process.exit(1);
}

const headerVersion = patched.match(/PATCHED COPY of livekit-client@([0-9.]+)/)?.[1];

// All fix markers that must be present in the patched bundle.
const markers = [
  ['negotiation id-0 fix', 'offerId > checkpoint || offerId === 0'],
  ['peerConnectionTimeout 60s master default', 'peerConnectionTimeout: 60000'],
  ['websocketTimeout 60s (defaults + joins)', 'websocketTimeout: 60000'],
  ['waitForNextEngineRestart 60s', 'arguments[0] : 60000;'],
  ['publishTrack timer 60s', '}, 60000);'],
];

if (headerVersion !== installedVersion) {
  console.error(
    `❌ Patched livekit-client bundle is for v${headerVersion} but node_modules has ` +
      `v${installedVersion}.\n` +
      '   The Vite alias would silently bundle the stale SDK.\n' +
      '   Regenerate the patch: python3 patches/patch-livekit-client.py',
  );
  process.exit(1);
}

const missing = markers.filter(([, needle]) => !patched.includes(needle));
if (missing.length > 0) {
  console.error(
    '❌ Patched bundle is missing required fix markers:\n' +
      missing.map(([label]) => `   - ${label}`).join('\n') +
      '\n   Regenerate: python3 patches/patch-livekit-client.py',
  );
  process.exit(1);
}

// No 15s connection-drop timeout may remain (allowlist: backoff/RPC/chunk are
// not connection-drop timers and keep their upstream values).
const banned = ['peerConnectionTimeout: 15000', 'websocketTimeout: 15000', 'arguments[0] : 15000', '}, 15000);'];
const stillThere = banned.filter((needle) => patched.includes(needle));
if (stillThere.length > 0) {
  console.error(
    '❌ Patched bundle still contains 15s connection-drop timeout(s):\n' +
      stillThere.map((needle) => `   - ${needle}`).join('\n') +
      '\n   Regenerate: python3 patches/patch-livekit-client.py',
  );
  process.exit(1);
}

console.log(`✅ livekit-client patch OK (v${installedVersion}, all ${markers.length} fix markers present, no 15s timeouts)`);
