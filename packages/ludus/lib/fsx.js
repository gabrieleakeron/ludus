'use strict';

// Tiny cross-platform fs helpers (recursive copy + remove) using only Node
// core APIs. Node >=22 ships fs.cpSync and fs.rmSync with recursive support,
// so no third-party deps are needed.

const fs = require('fs');

/** Recursively remove a path if it exists. No-op otherwise. */
function removeRecursive(targetPath) {
  if (fs.existsSync(targetPath)) {
    fs.rmSync(targetPath, { recursive: true, force: true });
  }
}

/** Recursively copy srcDir -> destDir, creating destDir's parents as needed. */
function copyRecursive(srcDir, destDir) {
  fs.mkdirSync(destDir, { recursive: true });
  fs.cpSync(srcDir, destDir, { recursive: true });
}

module.exports = { removeRecursive, copyRecursive };
