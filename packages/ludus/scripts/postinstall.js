#!/usr/bin/env node
'use strict';

// npm postinstall hook: best-effort install of the Claude plugin into
// ~/.claude/skills/ludus, using the exact same code path as `ludus setup`
// (lib/install.js#installPlugin). This must NEVER cause `npm install` to
// fail — worst case we print a warning and exit 0, because:
//   - CI environments may run with --ignore-scripts (this file then never
//     executes at all, which is fine — `ludus setup` covers it later).
//   - Some environments have no writable/known HOME (containers, some CI
//     runners) — skip cleanly rather than throwing.
//   - The bin must work even if this hook never ran, or failed partway.

const { installPlugin } = require('../lib/install');
const { homeDir } = require('../lib/paths');

function main() {
  // Skip quietly in environments with no meaningful home directory to write
  // into (best-effort — don't guess wrong and blow up the parent install).
  const home = homeDir();
  if (!home) {
    console.warn('ludus: postinstall skipped (no HOME/USERPROFILE detected).');
    return;
  }

  const result = installPlugin();
  if (result.ok) {
    console.log(`ludus: installed Claude plugin into ${result.dest}`);
    console.log('ludus: run "ludus up" to start the board (backend + mcp + frontend).');
  } else {
    // Warn, never throw: a postinstall failure must not fail `npm install`.
    console.warn(`ludus: postinstall could not install the Claude plugin (${result.reason})`);
    console.warn('ludus: you can retry manually later with "ludus setup".');
  }
}

try {
  main();
} catch (err) {
  console.warn(`ludus: postinstall skipped due to an unexpected error: ${err && err.message}`);
}

// Always exit 0 — postinstall must never fail the npm install.
process.exit(0);
