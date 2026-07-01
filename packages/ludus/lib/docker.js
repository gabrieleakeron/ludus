'use strict';

// Docker / Compose v2 discovery and invocation helpers. Cross-platform via
// child_process.spawnSync (no shell string-building, so Windows vs POSIX
// quoting differences don't matter).

const { spawnSync } = require('child_process');

/**
 * Check that `docker` is on PATH and the daemon is reachable, and that the
 * `docker compose` (v2, plugin form — not the legacy `docker-compose`
 * binary) subcommand is available.
 *
 * Returns { ok: true } or { ok: false, message } with a short, friendly,
 * non-stacktrace explanation suitable for printing directly to the user.
 */
function checkDockerAvailable() {
  let versionResult;
  try {
    versionResult = spawnSync('docker', ['version', '--format', '{{.Server.Version}}'], {
      encoding: 'utf8',
    });
  } catch (err) {
    return {
      ok: false,
      message:
        'Docker does not appear to be installed (the "docker" command was not found on PATH). ' +
        'Install Docker Desktop (or Docker Engine) and try again: https://docs.docker.com/get-docker/',
    };
  }

  if (versionResult.error && versionResult.error.code === 'ENOENT') {
    return {
      ok: false,
      message:
        'Docker does not appear to be installed (the "docker" command was not found on PATH). ' +
        'Install Docker Desktop (or Docker Engine) and try again: https://docs.docker.com/get-docker/',
    };
  }

  if (versionResult.status !== 0) {
    return {
      ok: false,
      message:
        'Docker is installed but the daemon is not reachable. Start Docker Desktop ' +
        '(or the Docker service) and try again.',
    };
  }

  let composeResult;
  try {
    composeResult = spawnSync('docker', ['compose', 'version'], { encoding: 'utf8' });
  } catch (err) {
    composeResult = { status: 1 };
  }

  if (!composeResult || composeResult.status !== 0) {
    return {
      ok: false,
      message:
        'Docker Compose v2 (the "docker compose" plugin) is not available. ' +
        'Update Docker Desktop, or install the compose plugin, and try again.',
    };
  }

  return { ok: true };
}

/**
 * Run `docker compose -f <composeFile> <...args>`, streaming output straight
 * to the parent's stdio. Returns the numeric exit code (0 on success).
 */
function runCompose(composeFile, args) {
  const result = spawnSync('docker', ['compose', '-f', composeFile, ...args], {
    stdio: 'inherit',
  });
  if (result.error) {
    console.error(`ludus: failed to run docker compose: ${result.error.message}`);
    return 1;
  }
  return result.status === null ? 1 : result.status;
}

module.exports = { checkDockerAvailable, runCompose };
