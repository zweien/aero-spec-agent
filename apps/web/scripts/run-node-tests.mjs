import { readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const sourceRoot = join(root, "src");

function findTestFiles(directory) {
  const entries = readdirSync(directory, { withFileTypes: true });
  const files = [];

  for (const entry of entries) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      files.push(...findTestFiles(path));
      continue;
    }

    if (entry.isFile() && entry.name.endsWith(".test.ts")) {
      files.push(path);
    }
  }

  return files.sort();
}

const testFiles = findTestFiles(sourceRoot);

if (testFiles.length === 0) {
  console.error("No frontend test files found.");
  process.exit(1);
}

const result = spawnSync(
  process.execPath,
  ["--test", "--experimental-strip-types", ...testFiles],
  { stdio: "inherit" },
);

process.exit(result.status ?? 1);
