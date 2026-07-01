#!/usr/bin/env node
'use strict';

// Ludus installer CLI.
//
// Subcommands: setup, up, down, status. Also --version/-v and --help/-h.
// Hand-rolled arg parsing on purpose — this CLI has zero runtime npm
// dependencies (see packages/ludus/package.json / README for the rationale).

const pkg = require('../package.json');
const { installPlugin } = require('../lib/install');
const { composeFile } = require('../lib/paths');
const { checkDockerAvailable, runCompose } = require('../lib/docker');

const HELP = `ludus ${pkg.version} — installer CLI for Ludus AI

Usage:
  ludus <command> [options]

Commands:
  setup     Install the Claude plugin into ~/.claude/skills/ludus
  up        Start the board (backend + mcp + frontend) via Docker Compose,
            pulling images from Docker Hub
  down      Stop and remove the board's containers
  status    Show the board's container status

Options:
  -v, --version   Print the installed version
  -h, --help      Show this help message

Examples:
  ludus setup
  ludus up
  ludus status
  ludus down
`;

function printHelp() {
  console.log(HELP);
}

function printVersion() {
  console.log(pkg.version);
}

function cmdSetup() {
  const result = installPlugin();
  if (!result.ok) {
    console.error(`ludus setup: failed to install the Claude plugin (${result.reason})`);
    process.exitCode = 1;
    return;
  }

  console.log(`ludus setup: installed Claude plugin into ${result.dest}`);
  console.log('');
  console.log('In Claude Code, run /reload-plugins (or restart it) to load the ludus');
  console.log('command (/ludus-create-scenario) and MCP server.');
  console.log('');
  console.log('Next steps:');
  console.log('  ludus up        # start the board (backend :8000, mcp :8765, frontend :8080)');
  console.log('  ludus status    # check container health');
}

function withDockerPreflight(fn) {
  const check = checkDockerAvailable();
  if (!check.ok) {
    console.error(`ludus: ${check.message}`);
    process.exitCode = 1;
    return;
  }
  fn();
}

function cmdUp() {
  withDockerPreflight(() => {
    const file = composeFile();
    console.log(`ludus up: starting the board from ${file} (pulling images from Docker Hub)...`);
    const code = runCompose(file, ['up', '-d']);
    if (code === 0) {
      console.log('');
      console.log('Board is up:');
      console.log('  backend   http://localhost:8000 (docs at /docs)');
      console.log('  mcp       http://localhost:8765/mcp');
      console.log('  frontend  http://localhost:8080');
    }
    process.exitCode = code;
  });
}

function cmdDown() {
  withDockerPreflight(() => {
    const file = composeFile();
    console.log(`ludus down: stopping the board (${file})...`);
    process.exitCode = runCompose(file, ['down']);
  });
}

function cmdStatus() {
  withDockerPreflight(() => {
    const file = composeFile();
    process.exitCode = runCompose(file, ['ps']);
  });
}

function main(argv) {
  const args = argv.slice(2);
  const first = args[0];

  if (!first || first === '-h' || first === '--help' || first === 'help') {
    printHelp();
    return;
  }

  if (first === '-v' || first === '--version' || first === 'version') {
    printVersion();
    return;
  }

  switch (first) {
    case 'setup':
      cmdSetup();
      break;
    case 'up':
      cmdUp();
      break;
    case 'down':
      cmdDown();
      break;
    case 'status':
      cmdStatus();
      break;
    default:
      console.error(`ludus: unknown command "${first}"\n`);
      printHelp();
      process.exitCode = 1;
  }
}

main(process.argv);
