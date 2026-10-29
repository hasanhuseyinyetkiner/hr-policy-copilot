/**
 * Regenerate the real HR Policy Copilot demo, without using the normal app data.
 *
 * Usage: node scripts/record-demo.mjs [--output /absolute/path/demo.gif]
 * Default output and all intermediate files are retained in a new OS temp directory.
 * --output copies the GIF to a new file and refuses to overwrite an existing file.
 *
 * Prerequisites: Node.js 20+, frontend dependencies (including @playwright/test and
 * Vite), Playwright Chromium + its video encoder, backend/.venv with the backend
 * dependencies, the local models/all-MiniLM-L6-v2 model, and ffmpeg on PATH.
 * Install Chromium with the project's Playwright CLI if needed. Supported on Windows,
 * macOS and Linux; no Docker, external Qdrant server, or running app is required.
 */
import { spawn } from 'node:child_process';
import { constants, createWriteStream } from 'node:fs';
import { access, copyFile, cp, mkdtemp, mkdir, stat, writeFile } from 'node:fs/promises';
import { createServer as createHttpServer, request } from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const frontend = path.join(root, 'frontend');
const backend = path.join(root, 'backend');
const requireFrontend = createRequire(path.join(frontend, 'package.json'));
const args = process.argv.slice(2);
if (args.includes('--help')) {
  console.log('Usage: node scripts/record-demo.mjs [--output /absolute/path/demo.gif]\nOutput is never overwritten; temp files and logs are retained. See script header for prerequisites.');
  process.exit(0);
}
if (args.length && (args.length !== 2 || args[0] !== '--output' || !path.isAbsolute(args[1]))) {
  console.error('Usage: node scripts/record-demo.mjs [--output /absolute/path/demo.gif]');
  process.exit(2);
}
const output = args[1];
let runDir;
let proxy;
let browser;
let context;
const children = [];
let interrupted = false;
for (const sig of ['SIGINT', 'SIGTERM']) process.on(sig, () => {
  if (!interrupted) { interrupted = true; console.error(`Received ${sig}; shutting down.`); }
});

function checkInterrupted() { if (interrupted) throw new Error('Interrupted'); }
function wait(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
async function exists(file, description) {
  try { await access(file); } catch { throw new Error(`Missing ${description}: ${file}`); }
}
function start(name, executable, argv, options) {
  const log = createWriteStream(path.join(runDir, `${name}.log`));
  const child = spawn(executable, argv, { ...options, windowsHide: true, detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe'] });
  const item = { name, child, log, text: '', error: null, closed: false };
  children.push(item);
  for (const stream of [child.stdout, child.stderr]) stream.on('data', chunk => {
    log.write(chunk);
    item.text = (item.text + chunk.toString()).slice(-100000);
  });
  child.on('error', error => { item.error = error; });
  child.on('close', () => { item.closed = true; log.end(); });
  return item;
}
async function waitForLog(item, pattern, timeout) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    checkInterrupted();
    if (item.error || item.closed || item.child.exitCode !== null) throw new Error(`${item.name} exited before starting: ${item.error || item.text.slice(-2000)}`);
    if (pattern.test(item.text)) return;
    await wait(200);
  }
  throw new Error(`Timed out waiting for ${item.name}; see ${item.name}.log`);
}
async function stop(item) {
  const child = item.child;
  if (!child.pid || item.closed || child.exitCode !== null) return;
  if (process.platform === 'win32') {
    // Target only the child tree we created. taskkill is hidden as well.
    await new Promise(resolve => {
      const killer = spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], { windowsHide: true, stdio: 'ignore' });
      killer.on('error', resolve); killer.on('close', resolve);
    });
  } else {
    try { process.kill(-child.pid, 'SIGTERM'); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    for (let i = 0; i < 50 && !item.closed; i++) await wait(100);
    if (!item.closed) { try { process.kill(-child.pid, 'SIGKILL'); } catch (error) { if (error.code !== 'ESRCH') throw error; } }
  }
  for (let i = 0; i < 50 && !item.closed; i++) await wait(100);
  if (!item.closed) throw new Error(`Could not confirm ${item.name} stopped (PID ${child.pid})`);
}
async function run() {
  runDir = await mkdtemp(path.join(os.tmpdir(), 'hr-policy-record-'));
  console.log(`Retained run directory: ${runDir}`);
  const python = path.join(backend, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const model = path.join(root, 'models', 'all-MiniLM-L6-v2');
  await exists(python, 'backend virtual environment Python');
  await exists(path.join(model, 'modules.json'), 'local embedding model');
  await exists(path.join(root, 'data', 'demo', 'manifest.json'), 'synthetic demo data');
  let playwright, vite, react, tailwind;
  try {
    playwright = requireFrontend('@playwright/test');
    vite = path.join(path.dirname(requireFrontend.resolve('vite/package.json')), 'bin', 'vite.js');
    react = requireFrontend.resolve('@vitejs/plugin-react');
    tailwind = requireFrontend.resolve('@tailwindcss/vite');
  } catch (error) { throw new Error(`Frontend dependencies are missing: ${error.message}`); }
  await cp(path.join(root, 'data', 'demo'), path.join(runDir, 'demo'), { recursive: true, dereference: true });
  await mkdir(path.join(runDir, 'uploads'));
  const config = path.join(runDir, 'vite.config.mjs');
  await writeFile(config, `import react from ${JSON.stringify(pathToFileURL(react).href)};\nimport tailwind from ${JSON.stringify(pathToFileURL(tailwind).href)};\nexport default { plugins: [react(), tailwind()], cacheDir: ${JSON.stringify(path.join(runDir, 'vite-cache'))}, server: { host: '127.0.0.1', strictPort: true, hmr: false } };\n`);
  // Bind inside the backend process so readiness cannot reach another server.
  const bootstrap = path.join(runDir, 'backend-bootstrap.py');
  await writeFile(bootstrap, `import socket, uvicorn\nsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\nsock.bind(('127.0.0.1', 0))\nsock.listen(128)\nprint('API_BOUND:', sock.getsockname()[1], flush=True)\nuvicorn.Server(uvicorn.Config('app.main:app', host='127.0.0.1', log_level='info')).run(sockets=[sock])\n`);
  const env = { ...process.env, APP_ENV: 'demo', API_HOST: '127.0.0.1', API_PORT: '0', ALLOW_NETWORK_BIND: 'false',
    DATABASE_URL: `sqlite:///${path.join(runDir, 'demo.sqlite3').replaceAll('\\', '/')}`,
    QDRANT_MODE: 'local', QDRANT_PATH: path.join(runDir, 'qdrant'), QDRANT_URL: 'http://127.0.0.1:9', QDRANT_WAIT: 'false',
    EMBEDDING_BACKEND: 'local', MODEL_DIR: model, HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1',
    HF_HOME: path.join(runDir, 'huggingface'), DEMO_DATA_DIR: path.join(runDir, 'demo'), UPLOAD_DIR: path.join(runDir, 'uploads'),
    SEED_ON_STARTUP: 'true', PYTHONPATH: backend, PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1', FAULT_INJECT: '', INGEST_DEBUG_SLEEP_SECONDS: '0' };
  const api = start('api', python, [bootstrap], { cwd: backend, env });
  const web = start('vite', process.execPath, [vite, '--config', config, '--host', '127.0.0.1', '--port', '0', '--strictPort'], { cwd: frontend, env: { ...process.env, NODE_ENV: 'development' } });
  await Promise.all([waitForLog(api, /API_BOUND: (\d+)/, 30000), waitForLog(web, /Local:\s+http:\/\/127\.0\.0\.1:(\d+)/, 120000)]);
  const apiPort = Number(api.text.match(/API_BOUND: (\d+)/)[1]);
  const vitePort = Number(web.text.match(/Local:\s+http:\/\/127\.0\.0\.1:(\d+)/)[1]);
  // The socket remains bound by our child throughout its lifetime.
  const deadline = Date.now() + 240000;
  let ready = false;
  while (Date.now() < deadline && !ready) {
    checkInterrupted();
    if (api.closed || api.child.exitCode !== null) throw new Error(`API exited during startup: ${api.text.slice(-2000)}`);
    ready = await new Promise(resolve => {
      const probe = request({ hostname: '127.0.0.1', port: apiPort, path: '/ready', timeout: 1000 }, response => { response.resume(); resolve(response.statusCode === 200); });
      probe.on('timeout', () => probe.destroy());
      probe.on('error', () => resolve(false));
      probe.end();
    });
    if (!ready) await wait(500);
  }
  if (!ready) throw new Error('Timed out waiting for the isolated API; see api.log');
  checkInterrupted();
  proxy = createHttpServer((req, res) => {
    if (api.closed || web.closed || api.child.exitCode !== null || web.child.exitCode !== null) { res.writeHead(503); res.end('Recording server exited'); return; }
    const port = /^\/(?:api|health|ready)(?:[/?]|$)/.test(req.url) ? apiPort : vitePort;
    const upstream = request({ hostname: '127.0.0.1', port, path: req.url, method: req.method, headers: { ...req.headers, host: `127.0.0.1:${port}` } }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res); });
    upstream.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end('Recording upstream unavailable'); });
    req.on('error', () => upstream.destroy());
    req.pipe(upstream);
  });
  await new Promise((resolve, reject) => { proxy.once('error', reject); proxy.listen(0, '127.0.0.1', resolve); });
  const port = proxy.address().port;
  console.log(`Recording isolated app on loopback ports ${apiPort}, ${vitePort}, ${port}`);
  browser = await playwright.chromium.launch({ headless: true });
  context = await browser.newContext({ viewport: { width: 1280, height: 800 }, recordVideo: { dir: runDir, size: { width: 1280, height: 800 } } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => { if (response.url().includes('/api/') && response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
  // Do not permit requests to any other server, including the app's default ports.
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    return url.hostname === '127.0.0.1' && url.port === String(port) ? route.continue() : route.abort();
  });
  const video = page.video();
  await page.goto(`http://127.0.0.1:${port}/`, { waitUntil: 'networkidle' });
  const { expect } = playwright;
  await expect(page.getByText('Local demo · synthetic data')).toBeVisible();
  await expect(page.getByText('Indexed documents')).toBeVisible();
  await page.waitForTimeout(1800);
  await page.getByRole('link', { name: 'Ask', exact: true }).click();
  await expect(page.getByLabel('Policy question')).toBeVisible();
  await page.waitForTimeout(700);
  await page.getByLabel('Policy question').pressSequentially('How many days of annual leave does a full-time employee receive?', { delay: 35 });
  await page.waitForTimeout(700);
  await page.getByRole('button', { name: 'Ask', exact: true }).click();
  await expect(page.getByTestId('answer')).toContainText('25 days of annual leave', { timeout: 60000 });
  await expect(page.getByTestId('answer')).toContainText('hybrid retrieval');
  await expect(page.getByTestId('citation-link').first()).toBeVisible();
  await page.waitForTimeout(3000);
  await page.getByTestId('citation-link').first().click();
  await expect(page.getByTestId('cited-passage')).toContainText('25 days of annual leave');
  await page.waitForTimeout(3500);
  if (errors.length) throw new Error(errors.join('\n'));
  checkInterrupted();
  await page.screenshot({ path: path.join(runDir, 'final.png') });
  await context.close(); context = undefined;
  const videoPath = await video.path();
  await browser.close(); browser = undefined;
  const gif = path.join(runDir, 'demo.gif');
  const ffmpeg = start('ffmpeg', 'ffmpeg', ['-hide_banner', '-loglevel', 'warning', '-y', '-i', videoPath, '-filter_complex', 'fps=8,scale=960:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle', '-loop', '0', gif], { cwd: runDir, env: process.env });
  while (!ffmpeg.closed) { checkInterrupted(); if (ffmpeg.error) throw ffmpeg.error; await wait(200); }
  if (ffmpeg.child.exitCode !== 0) throw new Error(`ffmpeg failed: ${ffmpeg.text.slice(-2000)}`);
  console.log(`GIF: ${gif} (${((await stat(gif)).size / 1024 / 1024).toFixed(2)} MiB)`);
  if (output) { await copyFile(gif, output, constants.COPYFILE_EXCL); console.log(`Copied GIF to new file: ${output}`); }
  console.log('Verified: home → ask → evidence-backed answer → cited passage.');
}
try { await run(); } catch (error) { console.error(error.stack || error); process.exitCode = 1; }
finally {
  if (context) await context.close().catch(error => console.error('Context close:', error));
  if (browser) await browser.close().catch(error => console.error('Browser close:', error));
  if (proxy?.listening) await new Promise(resolve => proxy.close(resolve));
  for (const child of children.reverse()) {
    try { await stop(child); } catch (error) { console.error(error); process.exitCode = 1; }
  }
  if (runDir) console.log(`Retained all run files: ${runDir}`);
}
