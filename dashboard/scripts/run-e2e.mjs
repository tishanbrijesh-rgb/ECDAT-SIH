import { spawn } from "node:child_process";
import { once } from "node:events";
import { fileURLToPath } from "node:url";

const host = "127.0.0.1";
const port = 4173;
const baseUrl = `http://${host}:${port}`;
const viteCli = fileURLToPath(new URL("../node_modules/vite/bin/vite.js", import.meta.url));
const playwrightCli = fileURLToPath(
  new URL("../node_modules/@playwright/test/cli.js", import.meta.url),
);

const server = spawn(process.execPath, [viteCli, "--host", host, "--port", String(port)], {
  stdio: "inherit",
});

async function waitForServer() {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (server.exitCode !== null) {
      throw new Error(`Vite exited before becoming ready (code ${server.exitCode}).`);
    }
    try {
      const response = await fetch(baseUrl);
      if (response.ok) return;
    } catch {
      // The server is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error(`Timed out waiting for ${baseUrl}.`);
}

async function stopServer() {
  if (server.exitCode !== null) return;
  server.kill();
  await Promise.race([once(server, "exit"), new Promise((resolve) => setTimeout(resolve, 5_000))]);
  if (server.exitCode === null) server.kill("SIGKILL");
}

let exitCode = 1;
try {
  await waitForServer();
  const runner = spawn(process.execPath, [playwrightCli, "test", ...process.argv.slice(2)], {
    env: { ...process.env, ECDAT_E2E_EXTERNAL_SERVER: "1" },
    stdio: "inherit",
  });
  const [code] = await once(runner, "exit");
  exitCode = code ?? 1;
} finally {
  await stopServer();
}

process.exitCode = exitCode;
