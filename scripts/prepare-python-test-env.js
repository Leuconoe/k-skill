const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");
const venv = path.join(root, ".cache", "python-test-venv");

function resolveSystemPython() {
  for (const command of ["python3", "python"]) {
    const result = spawnSync(command, ["--version"], { encoding: "utf8" });
    if (result.status === 0) {
      return command;
    }
  }
  throw new Error("python3 or python is required to prepare the test virtualenv.");
}

function resolveVenvPython() {
  const windowsPython = path.join(venv, "Scripts", "python.exe");
  const unixPython = path.join(venv, "bin", "python");
  if (fs.existsSync(windowsPython)) {
    return windowsPython;
  }
  if (fs.existsSync(unixPython)) {
    return unixPython;
  }
  throw new Error("python test virtualenv exists but no interpreter was found.");
}

fs.mkdirSync(path.dirname(venv), { recursive: true });
if (!fs.existsSync(path.join(venv, "pyvenv.cfg"))) {
  const created = spawnSync(resolveSystemPython(), ["-m", "venv", venv], {
    cwd: root,
    stdio: "inherit"
  });
  if (created.status !== 0) {
    process.exit(created.status ?? 1);
  }
}

const pip = spawnSync(
  resolveVenvPython(),
  ["-m", "pip", "install", "--quiet", "beautifulsoup4", "openpyxl==3.1.5", "SRTrain==2.6.7"],
  { cwd: root, stdio: "inherit" }
);
if (pip.status !== 0) {
  process.exit(pip.status ?? 1);
}
