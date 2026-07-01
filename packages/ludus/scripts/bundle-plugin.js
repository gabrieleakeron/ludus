#!/usr/bin/env node
'use strict';

// prepack step: copy the sibling ../ludus-claude-plugin (a dev-checkout-only
// sibling package, NOT published to npm) into assets/ludus-claude-plugin so
// that the tarball produced by `npm pack` is self-contained. This mirrors
// the plugin-bundling pattern used by other Claude Code plugin installers
// in the broader ecosystem. There is no "preview app" for Ludus (the board
// is pulled from Docker Hub at `ludus up` time), so there is deliberately no
// separate preview-bundling script here — only the plugin gets bundled.

const fs = require('fs');
const path = require('path');
const { copyRecursive, removeRecursive } = require('../lib/fsx');

const packageRoot = path.join(__dirname, '..');
const src = path.join(packageRoot, '..', 'ludus-claude-plugin');
const dest = path.join(packageRoot, 'assets', 'ludus-claude-plugin');

function main() {
  if (!fs.existsSync(src)) {
    console.error(
      `bundle-plugin: sibling plugin not found at ${src}\n` +
        'This script must run from a full checkout of the ludus repo ' +
        '(packages/ludus-claude-plugin must exist alongside packages/ludus).'
    );
    process.exit(1);
  }

  removeRecursive(dest);
  copyRecursive(src, dest);

  console.log(`bundle-plugin: copied ${src} -> ${dest}`);
}

main();
