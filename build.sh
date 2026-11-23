#!/usr/bin/env bash
# Render.com build script — builds Angular then installs Python deps.
# Set as Build Command: bash build.sh
# Set Start Command:    cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT --ws-max-size 8192 --no-proxy-headers
#   --ws-max-size caps each incoming WebSocket message at 8 KiB (uvicorn's
#   default is 16 MiB). --no-proxy-headers keeps uvicorn from replacing the
#   client address with the leftmost, client-chosen X-Forwarded-For entry
#   (Render trusts every peer). Keep a single worker: limits are kept per process.
set -e

echo "==> Building Angular frontend..."
cd frontend
npm ci
npx ng build --configuration production
# Stops the deploy if the link-preview tags or og-image.png are missing.
node scripts/check-og-tags.mjs

echo "==> Copying static files to backend..."
mkdir -p ../backend/static
cp -r dist/signal-forge/browser/. ../backend/static/

echo "==> Installing Python dependencies..."
cd ../backend
pip install -r requirements.txt

echo "==> Build complete."
