#!/usr/bin/env bash
# Render.com build script — builds Angular then installs Python deps.
# Set as Build Command: bash build.sh
# Set Start Command:    cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
set -e

echo "==> Building Angular frontend..."
cd frontend
npm ci
npx ng build --configuration production

echo "==> Copying static files to backend..."
mkdir -p ../backend/static
cp -r dist/signal-forge/browser/. ../backend/static/

echo "==> Installing Python dependencies..."
cd ../backend
pip install -r requirements.txt

echo "==> Build complete."
