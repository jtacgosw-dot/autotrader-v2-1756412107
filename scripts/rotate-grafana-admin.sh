#!/bin/bash

NEW_ADMIN_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-20)

aws secretsmanager create-secret \
  --name "autotrader/grafana-admin" \
  --description "Grafana admin credentials" \
  --secret-string "{\"username\":\"admin\",\"password\":\"$NEW_ADMIN_PASSWORD\"}" \
  --tags '[{"Key":"Stack","Value":"autotrader-v2"},{"Key":"Env","Value":"prod"}]' \
  --region us-east-1

echo "New Grafana admin password stored in Secrets Manager"
echo "Password: $NEW_ADMIN_PASSWORD"
echo "Please update GRAFANA_ADMIN_PASSWORD environment variable and restart Grafana"
