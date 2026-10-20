import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function rmBestEffort(target: string) {
  try {
    fs.rmSync(target, { recursive: true, force: true });
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "EPERM" || code === "EBUSY" || code === "ENOTEMPTY") {
      const quarantine = `${target}.stale-${Date.now()}`;
      try {
        fs.renameSync(target, quarantine);
      } catch {
        // Leave locked files; this run uses a fresh path from playwright.config.
      }
      return;
    }
    throw error;
  }
}

export default function globalSetup() {
  for (const relative of ["data/e2e.sqlite3", "data/e2e.sqlite3-wal", "data/e2e.sqlite3-shm"]) {
    rmBestEffort(path.join(repoRoot, relative));
  }
  const dataDir = path.join(repoRoot, "data");
  if (fs.existsSync(dataDir)) {
    for (const name of fs.readdirSync(dataDir)) {
      if (name.startsWith("qdrant-e2e") || name.startsWith("uploads-e2e")) {
        rmBestEffort(path.join(dataDir, name));
      }
    }
  }
  fs.mkdirSync(path.join(repoRoot, "docs", "screenshots"), { recursive: true });
}
