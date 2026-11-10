#!/usr/bin/env bash
# One-time bootstrap for a fresh Oracle Cloud Ubuntu VM (ARM Ampere A1 or AMD).
# Run on the server:  bash setup.sh
set -euo pipefail

echo "==> System update"
sudo apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
sudo apt-get install -y git curl iptables-persistent

echo "==> Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"

echo "==> Host firewall: Oracle's Ubuntu image blocks everything but SSH in iptables"
for port in 80 443; do
  if ! sudo iptables -C INPUT -p tcp -m state --state NEW --dport "$port" -j ACCEPT 2>/dev/null; then
    sudo iptables -I INPUT 6 -p tcp -m state --state NEW --dport "$port" -j ACCEPT
  fi
done
sudo netfilter-persistent save

echo "==> Swap (2 GB) so builds never run out of memory"
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

echo "==> App folder"
sudo mkdir -p /opt/apps && sudo chown "$USER" /opt/apps
cd /opt/apps
[ -d The-Decision-Engine ] || git clone https://github.com/AhmedSAAhmed/The-Decision-Engine.git
cp -n The-Decision-Engine/deploy/oracle/docker-compose.yml .
cp -n The-Decision-Engine/deploy/oracle/Caddyfile .
cp -n The-Decision-Engine/deploy/oracle/.env.example .env

echo
echo "Done. Next:"
echo "  1. Log out and back in (so 'docker' works without sudo)"
echo "  2. nano /opt/apps/.env       -> set DOMAIN and EMAIL"
echo "  3. cd /opt/apps && docker compose up -d --build"
