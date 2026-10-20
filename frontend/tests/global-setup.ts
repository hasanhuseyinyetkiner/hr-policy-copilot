import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

export default function globalSetup() {
  for (const relative of ["data/e2e.sqlite3", "data/e2e.sqlite3-wal", "data/e2e.sqlite3-shm"]) {
    fs.rmSync(path.join(repoRoot, relative), { force: true });
  }
  fs.rmSync(path.join(repoRoot, "data", "qdrant-e2e"), { recursive: true, force: true });
  fs.rmSync(path.join(repoRoot, "data", "uploads-e2e"), { recursive: true, force: true });
  fs.mkdirSync(path.join(repoRoot, "docs", "screenshots"), { recursive: true });
}
