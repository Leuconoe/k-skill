const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const venv = path.join(__dirname, "..", ".cache", "python-test-venv");
const windowsPython = path.join(venv, "Scripts", "python.exe");
const unixPython = path.join(venv, "bin", "python");
const python = fs.existsSync(windowsPython) ? windowsPython : unixPython;

if (!fs.existsSync(python)) {
  throw new Error("python test virtualenv is missing. Run `npm run prepare:python-test-env` first.");
}

const result = spawnSync(python, process.argv.slice(2), {
  stdio: "inherit",
  env: process.env
});
process.exit(result.status ?? 1);
