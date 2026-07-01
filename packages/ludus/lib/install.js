'use strict';

// Shared "install the Claude plugin" routine, used by both `ludus setup`
// (bin/ludus.js) and the npm postinstall hook (scripts/postinstall.js), so
// the two code paths can never drift.

const { bundledPluginDir, installedPluginDir, legacyInstalledPluginDir } = require('./paths');
const { removeRecursive, copyRecursive } = require('./fsx');

/**
 * Copy the bundled plugin into ~/.claude/skills/ludus, overwriting any previous
 * install (idempotent: remove-then-copy). That location is a "skills-directory
 * plugin": Claude Code auto-discovers it as `ludus@skills-dir` and loads its
 * commands + MCP server on the next session (or after `/reload-plugins`) — no
 * marketplace registration needed. The plugin's own `.mcp.json` (pointing at
 * http://localhost:8765/mcp) is copied as-is — we never rewrite it.
 *
 * Also removes the legacy ~/.claude/plugins/ludus copy left by ludus <= 0.1.0,
 * which Claude Code never loaded (best-effort — failure to clean it is ignored).
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
  } catch (err) {
    return { ok: false, reason: err && err.message ? err.message : String(err) };
  }

  // Best-effort cleanup of the pre-0.1.x location; never fatal.
  try {
    removeRecursive(legacyInstalledPluginDir());
  } catch {
    // ignore — a leftover inert copy is harmless.
  }

  return { ok: true, dest, src };
}

module.exports = { installPlugin };
