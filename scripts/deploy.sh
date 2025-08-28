#!/bin/bash
set -e

echo "Starting AutoTrader deployment..."

cd /opt/autotrader

echo "Downloading deployment package..."
aws s3 cp s3://app.lunaraxolotl.com/deploy/autotrader-deploy.tar.gz .

echo "Extracting files..."
tar -xzf autotrader-deploy.tar.gz

echo "Starting Docker services..."
docker-compose pull
docker-compose up -d

echo "Waiting for services to start..."
sleep 10

echo "Checking nginx status..."
ss -ltnp | grep 8081

echo "Testing health endpoint..."
curl -sI http://127.0.0.1:8081/api/health

echo "Deployment complete!"
