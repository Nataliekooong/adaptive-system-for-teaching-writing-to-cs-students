import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const backendDir = join(root, "src", "backend");
const frontendDir = join(root, "src", "frontend");
const python = process.platform === "win32"
  ? join(backendDir, ".venv", "Scripts", "python.exe")
  : join(backendDir, ".venv", "bin", "python");
const frontendCommand = process.platform === "win32" ? process.env.ComSpec ?? "cmd.exe" : "npm";
const frontendArgs = process.platform === "win32"
  ? ["/d", "/s", "/c", "npm.cmd", "run", "dev", "--", "--host", "127.0.0.1", "--strictPort"]
  : ["run", "dev", "--", "--host", "127.0.0.1", "--strictPort"];

if (!existsSync(python)) {
  console.error("Backend environment not found. Run the setup steps in SETUP.md first.");
  process.exit(1);
}

const children = [
  spawn(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], {
    cwd: backendDir,
    stdio: "inherit",
  }),
  spawn(frontendCommand, frontendArgs, {
    cwd: frontendDir,
    stdio: "inherit",
  }),
];

let stopping = false;
function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (!child.killed) child.kill();
  }
  setTimeout(() => process.exit(exitCode), 250);
}

for (const child of children) {
  child.on("error", (error) => {
    console.error(error.message);
    stop(1);
  });
  child.on("exit", (code, signal) => {
    if (!stopping) stop(code ?? (signal ? 1 : 0));
  });
}

process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
