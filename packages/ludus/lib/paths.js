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

/** Destination for the installed plugin: ~/.claude/plugins/ludus */
function installedPluginDir() {
  return path.join(homeDir(), '.claude', 'plugins', 'ludus');
}

module.exports = {
  packageRoot,
  bundledPluginDir,
  composeFile,
  envExampleFile,
  homeDir,
  installedPluginDir,
};
