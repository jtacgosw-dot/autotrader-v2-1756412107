#!/bin/bash
set -e

echo "Setting up GitHub OIDC for AutoTrader CI/CD..."

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Creating OIDC identity provider..."
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --client-id-list sts.amazonaws.com \
  --tags Key=Stack,Value=autotrader-v2 Key=Env,Value=prod \
  2>/dev/null || echo "OIDC provider already exists"

echo "Creating IAM role for GitHub Actions..."
cat > /tmp/github-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:*/autotrader-v2:*"
        }
      }
    }
  ]
}
EOF

aws iam create-role \
  --role-name GitHubActionsAutoTrader \
  --assume-role-policy-document file:///tmp/github-trust-policy.json \
  --tags Key=Stack,Value=autotrader-v2 Key=Env,Value=prod

echo "Creating custom IAM policy..."
cat > /tmp/github-actions-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::app.lunaraxolotl.com",
        "arn:aws:s3:::app.lunaraxolotl.com/*",
        "arn:aws:s3:::autotrader-deploy-bucket-v2",
        "arn:aws:s3:::autotrader-deploy-bucket-v2/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudfront:CreateInvalidation",
        "cloudfront:GetInvalidation"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:SendCommand",
        "ssm:GetCommandInvocation"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name GitHubActionsAutoTraderPolicy \
  --policy-document file:///tmp/github-actions-policy.json \
  --tags Key=Stack,Value=autotrader-v2 Key=Env,Value=prod

aws iam attach-role-policy \
  --role-name GitHubActionsAutoTrader \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/GitHubActionsAutoTraderPolicy

echo "GitHub OIDC setup completed!"
echo "Role ARN: arn:aws:iam::${ACCOUNT_ID}:role/GitHubActionsAutoTrader"
echo "Add this ARN to your GitHub repository secrets as AWS_ROLE_ARN"

rm -f /tmp/github-trust-policy.json /tmp/github-actions-policy.json
