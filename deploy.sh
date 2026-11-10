#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# AiDocMaker - 1-Click Production Linux Deployment Script
# Targets: Ubuntu 22.04 / 24.04 LTS, Debian 12, AWS EC2, DigitalOcean, Linode
# ==============================================================================

echo "========================================================"
echo "   🚀 Starting AiDocMaker Linux Deployment"
echo "========================================================"

# 1. Check Root / Sudo
if [ "$EUID" -ne 0 ]; then
  SUDO="sudo"
else
  SUDO=""
fi

# 2. Check / Setup Swap Space (Prevents out-of-memory during builds)
if [ ! -f /swapfile ]; then
  echo "==> Configuring 2GB Swapfile..."
  $SUDO fallocate -l 2G /swapfile
  $SUDO chmod 600 /swapfile
  $SUDO mkswap /swapfile
  $SUDO swapon /swapfile
  echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab
  echo "✔ Swapfile created successfully."
else
  echo "✔ Swapfile already present."
fi

# 3. Check / Install Docker
if ! command -v docker &> /dev/null; then
  echo "==> Installing Docker Engine..."
  curl -fsSL https://get.docker.com -o get-docker.sh
  $SUDO sh get-docker.sh
  rm -f get-docker.sh
  $SUDO systemctl enable --now docker
  if [ -n "${SUDO_USER:-}" ]; then
    $SUDO usermod -aG docker "$SUDO_USER"
  fi
  echo "✔ Docker Engine installed."
else
  echo "✔ Docker is already installed: $(docker --version)"
fi

# 4. Check Environment Configuration (.env)
if [ ! -f .env ]; then
  echo "==> Creating .env from .env.example..."
  if [ -f .env.example ]; then
    cp .env.example .env
  else
    cat << 'EOF' > .env
ENVIRONMENT=production
DATABASE_URL=sqlite:////app/aiqms.db
AIQMS_STORAGE_DIR=/app/data
CORS_ORIGINS=http://localhost:5173,http://localhost:80,http://localhost
DEV_AUTH_ENABLED=true

# NVIDIA NIM API (Replace with your production key)
NVIDIA_API_KEY=
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=poolside/laguna-xs-2.1
NVIDIA_TIMEOUT=120
NVIDIA_MAX_RETRIES=2

# OpenRouter API
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
EOF
  fi
  echo "⚠ Please edit .env with your NVIDIA_API_KEY if not already set."
else
  echo "✔ Production .env file found."
fi

# 5. Build and Launch Containers
echo "==> Building and launching Docker Compose stack..."
$SUDO docker compose up -d --build

# 6. Wait for Containers to report healthy
echo "==> Waiting for API and Web services to initialize (15s)..."
sleep 15

# 7. Run Health Checks
echo "==> Performing Health Checks..."
if curl -s -f http://localhost:8000/api/v1/compliance/ml/model-info > /dev/null; then
  echo "✔ Backend API & ISO 13485 ML Model: HEALTHY"
else
  echo "❌ Backend API did not respond on http://localhost:8000"
fi

if curl -s -f -I http://localhost:80 > /dev/null; then
  echo "✔ Nginx Web Frontend (Port 80): HEALTHY"
else
  echo "❌ Frontend did not respond on http://localhost:80"
fi

echo "========================================================"
echo "   🎉 AiDocMaker Deployment Complete!"
echo "========================================================"
echo "   Web Application: http://YOUR_SERVER_IP"
echo "   API Swagger UI:  http://YOUR_SERVER_IP:8000/docs"
echo "   ML Model Status: http://YOUR_SERVER_IP:8000/api/v1/compliance/ml/model-info"
echo "========================================================"
