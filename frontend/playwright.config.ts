import { defineConfig } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(frontendRoot, "..");
const runId = `${Date.now()}-${process.pid}`;
const databaseFile = path.join(repoRoot, "data", `e2e-${runId}.sqlite3`);
const qdrantPath = path.join(repoRoot, "data", `qdrant-e2e-${runId}`);
const uploadDir = path.join(repoRoot, "data", `uploads-e2e-${runId}`);

export default defineConfig({
  testDir: "./tests",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  globalSetup: "./tests/global-setup.ts",
  use: {
    baseURL: "http://127.0.0.1:5101",
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  },
  webServer: [
    {
      command: "uv run python -m app",
      cwd: path.join(repoRoot, "backend"),
      url: "http://127.0.0.1:8101/ready",
      timeout: 240_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        APP_ENV: "demo",
        API_HOST: "127.0.0.1",
        API_PORT: "8101",
        ALLOW_NETWORK_BIND: "false",
        DATABASE_URL: `sqlite:///${databaseFile.replaceAll("\\", "/")}`,
        QDRANT_MODE: "local",
        QDRANT_PATH: qdrantPath,
        EMBEDDING_BACKEND: "local",
        MODEL_DIR: path.join(repoRoot, "models", "all-MiniLM-L6-v2"),
        HF_HUB_OFFLINE: "1",
        DEMO_DATA_DIR: path.join(repoRoot, "data", "demo"),
        UPLOAD_DIR: uploadDir,
        SEED_ON_STARTUP: "true",
        QDRANT_WAIT: "false",
      },
    },
    {
      command: "pnpm dev",
      cwd: frontendRoot,
      url: "http://127.0.0.1:5101",
      timeout: 120_000,
      reuseExistingServer: false,
    },
  ],
});
