#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.join(__dirname, "..");

function walkJs(dir, files = []) {
  if (!fs.existsSync(dir)) {
    return files;
  }
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules") continue;
      walkJs(full, files);
    } else if (entry.isFile() && entry.name.endsWith(".js")) {
      files.push(full);
    }
  }
  return files;
}

const files = ["src", "test", "scripts"]
  .flatMap((dir) => walkJs(path.join(root, dir)))
  .sort();

if (files.length === 0) {
  console.error("check-js: no JavaScript files found");
  process.exit(1);
}

const result = spawnSync(process.execPath, ["--check", ...files], {
  cwd: root,
  stdio: "inherit",
  windowsHide: true,
});
if (result.error) {
  console.error(result.error);
  process.exit(1);
}
process.exit(result.status ?? 1);
