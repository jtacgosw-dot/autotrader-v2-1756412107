#!/bin/bash
set -euxo pipefail
dnf -y update
dnf -y install amazon-ssm-agent docker
systemctl enable --now amazon-ssm-agent
systemctl enable --now docker
curl -fsSL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 \
  -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
mkdir -p /opt/autotrader
