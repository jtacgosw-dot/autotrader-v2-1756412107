#!/usr/bin/env python3
import boto3
import json

def create_least_privilege_policy():
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
                    "arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/discord-webhook-*",
                    "arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/viewer-credentials-*",
                    "arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/controller-credentials-*",
                    "arn:aws:secretsmanager:us-east-1:123198875719:secret:autotrader/grafana-admin-*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ssm:DescribeInstanceInformation"
                ],
                "Resource": "*",
                "Condition": {
                    "StringEquals": {
                        "ssm:resourceTag/Stack": "autotrader-v2"
                    }
                }
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": "arn:aws:logs:us-east-1:123198875719:log-group:/aws/autotrader/*"
            }
        ]
    }
    
    policy_response = iam.create_policy(
        PolicyName='AutoTraderLeastPrivilege',
        PolicyDocument=json.dumps(policy_document),
        Description='Least privilege policy for AutoTrader EC2 instances'
    )
    
    role_name = 'autotrader-ec2-role'
    
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn=policy_response['Policy']['Arn']
    )
    
    try:
        iam.detach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/SecretsManagerReadWrite'
        )
    except:
        pass
    
    print(f"Created least privilege policy: {policy_response['Policy']['Arn']}")
    return policy_response['Policy']['Arn']

if __name__ == "__main__":
    create_least_privilege_policy()
