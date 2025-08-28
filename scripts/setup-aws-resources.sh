#!/bin/bash
set -e

echo "Setting up AWS resources for AutoTrader v2..."

echo "Creating S3 bucket for audit logs..."
aws s3 mb s3://autotrader-audit-logs-v2 --region us-east-1

echo "Applying S3 lifecycle policy..."
aws s3api put-bucket-lifecycle-configuration \
  --bucket autotrader-audit-logs-v2 \
  --lifecycle-configuration '{
    "Rules": [
      {
        "ID": "audit-log-lifecycle",
        "Status": "Enabled",
        "Filter": {"Prefix": "audit-logs/"},
        "Transitions": [
          {
            "Days": 30,
            "StorageClass": "STANDARD_IA"
          },
          {
            "Days": 180,
            "StorageClass": "GLACIER"
          }
        ]
      }
    ]
  }'

echo "Applying S3 bucket tags..."
aws s3api put-bucket-tagging \
  --bucket autotrader-audit-logs-v2 \
  --tagging 'TagSet=[{"Key":"Stack","Value":"autotrader-v2"},{"Key":"Env","Value":"prod"}]'

echo "Creating S3 bucket for deployment artifacts..."
aws s3 mb s3://autotrader-deploy-bucket-v2 --region us-east-1

aws s3api put-bucket-tagging \
  --bucket autotrader-deploy-bucket-v2 \
  --tagging 'TagSet=[{"Key":"Stack","Value":"autotrader-v2"},{"Key":"Env","Value":"prod"}]'

echo "AWS resources setup completed!"
