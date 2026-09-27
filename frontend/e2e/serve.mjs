// Starts the app the way Render runs it, for the e2e tests: a production
// build served by the FastAPI backend (same origin), in demo mode, no DB.
// Used as Playwright's webServer; not for development.
import { execSync, spawn } from 'node:child_process';
import { cpSync, rmSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const backend = resolve(frontend, '../backend');
const port = process.env.E2E_PORT ?? '8765';
const python = process.env.BACKEND_PYTHON ?? resolve(backend, 'venv/bin/python');

execSync('npx ng build', { cwd: frontend, stdio: 'inherit' });
rmSync(resolve(backend, 'static'), { recursive: true, force: true });
cpSync(resolve(frontend, 'dist/signal-forge/browser'), resolve(backend, 'static'), { recursive: true });

const server = spawn(python, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', port], {
  cwd: backend,
  stdio: 'inherit',
  env: {
    ...process.env,
    DEMO_MODE: 'true',            // public demo accounts + Try-as buttons
    DATABASE_URL: '',             // in memory; never the developer's database
    JWT_SECRET: 'e2e-only-secret-never-used-in-production',
    ENV: 'development',           // plain-HTTP cookies on 127.0.0.1
    ABUSEIPDB_API_KEY: '', IPINFO_TOKEN: '', GROQ_API_KEY: '',
  },
});
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.kill(signal));
server.on('exit', code => process.exit(code ?? 0));
