'use strict';

// Shared "install the Claude plugin" routine, used by both `ludus setup`
// (bin/ludus.js) and the npm postinstall hook (scripts/postinstall.js), so
// the two code paths can never drift.

const { bundledPluginDir, installedPluginDir } = require('./paths');
const { removeRecursive, copyRecursive } = require('./fsx');

/**
 * Copy the bundled plugin into ~/.claude/plugins/ludus, overwriting any
 * previous install (idempotent: remove-then-copy). The plugin's own
 * `.mcp.json` (pointing at http://localhost:8765/mcp) is copied as-is —
 * we never rewrite it.
 *
 * Returns { ok: true, dest } on success, or { ok: false, reason } if the
 * bundled plugin source could not be found or the copy failed. Never throws
 * — callers (postinstall in particular) must be able to treat failure as a
 * warning, not a fatal error.
 */
function installPlugin() {
  const src = bundledPluginDir();
  if (!src) {
    return {
      ok: false,
      reason:
        'could not find the bundled Claude plugin (expected assets/ludus-claude-plugin ' +
        'inside the package, or ../ludus-claude-plugin in a dev checkout).',
    };
  }

  const dest = installedPluginDir();
  try {
    removeRecursive(dest);
    copyRecursive(src, dest);
    return { ok: true, dest, src };
  } catch (err) {
    return { ok: false, reason: err && err.message ? err.message : String(err) };
  }
}

module.exports = { installPlugin };
