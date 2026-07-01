'use strict';

// Central place for resolving filesystem locations the CLI/install code needs.
// Kept dependency-free (only Node core modules) and Windows/macOS/Linux safe.

const os = require('os');
const path = require('path');
const fs = require('fs');

/** Root of the installed `ludus` package (parent of lib/, bin/, assets/). */
function packageRoot() {
  return path.join(__dirname, '..');
}

/**
 * Path to the bundled Claude plugin inside this package.
 * Prefers the packed location (assets/ludus-claude-plugin, created by
 * prepack/bundle-plugin.js). Falls back to the sibling dev-checkout path
 * (../ludus-claude-plugin relative to packages/ludus) so `node bin/ludus.js`
 * works straight out of a git clone before `npm pack` has ever run.
 */
function bundledPluginDir() {
  const packed = path.join(packageRoot(), 'assets', 'ludus-claude-plugin');
  if (fs.existsSync(packed)) {
    return packed;
  }
  const devSibling = path.join(packageRoot(), '..', 'ludus-claude-plugin');
  if (fs.existsSync(devSibling)) {
    return devSibling;
  }
  return null;
}

/** Path to the bundled pull-based docker-compose file. */
function composeFile() {
  return path.join(packageRoot(), 'assets', 'docker-compose.yml');
}

/** Path to the bundled .env.example (not copied anywhere automatically). */
function envExampleFile() {
  return path.join(packageRoot(), 'assets', '.env.example');
}

/** The user's home directory, honoring HOME/USERPROFILE overrides (tests use this). */
function homeDir() {
  return process.env.HOME || process.env.USERPROFILE || os.homedir();
}

/**
 * Destination for the installed plugin: ~/.claude/skills/ludus
 *
 * This is a "skills-directory plugin" location: Claude Code auto-discovers any
 * folder under ~/.claude/skills/ that carries a .claude-plugin/plugin.json and
 * loads it as `ludus@skills-dir` (bringing its commands/ and .mcp.json with it)
 * on the next session — no marketplace, no install step. We deliberately do NOT
 * install under ~/.claude/plugins/ludus: files copied there are inert unless the
 * plugin is registered via a marketplace + enabledPlugins, which we don't ship.
 */
function installedPluginDir() {
  return path.join(homeDir(), '.claude', 'skills', 'ludus');
}

/**
 * Legacy destination used by ludus <= 0.1.0: ~/.claude/plugins/ludus. Files
 * copied here were never loaded by Claude Code. We clean it up on install so
 * upgraders don't keep a stale, invisible copy around.
 */
function legacyInstalledPluginDir() {
  return path.join(homeDir(), '.claude', 'plugins', 'ludus');
}

module.exports = {
  packageRoot,
  bundledPluginDir,
  composeFile,
  envExampleFile,
  homeDir,
  installedPluginDir,
  legacyInstalledPluginDir,
};
