#!/usr/bin/env python3
import boto3
import json

def create_iam_least_privilege_policy():
    """Create IAM least-privilege policy for AutoTrader EC2 role"""
    iam = boto3.client('iam')
    
    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue"
                ],
                "Resource": [
                    "arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/viewer-*",
                    "arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/controller-*",
                    "arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/binance-*",
                    "arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/kucoin-*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ssm:DescribeInstanceInformation"
                ],
                "Resource": "*"
            }
        ]
    }
    
    try:
        response = iam.put_role_policy(
            RoleName='EC2-SSM-Role',
            PolicyName='AutoTraderLeastPrivilege',
            PolicyDocument=json.dumps(policy_document)
        )
        print(f"✅ IAM least-privilege policy created/updated successfully")
        print(f"Policy attached to role: AutoTraderEC2Role")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create IAM policy: {e}")
        return False

if __name__ == "__main__":
    create_iam_least_privilege_policy()
