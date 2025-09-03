#!/usr/bin/env python3
import boto3
import json
import os
from datetime import datetime

def create_ami_snapshot():
    """Create AMI snapshot of current instance"""
    ec2 = boto3.client('ec2')
    instance_id = 'i-06051733a989e0abf'
    
    try:
        response = ec2.create_image(
            InstanceId=instance_id,
            Name=f'autotrader-backup-{datetime.now().strftime("%Y-%m-%d-%H%M")}',
            Description='AutoTrader production backup',
            NoReboot=True,
            TagSpecifications=[
                {
                    'ResourceType': 'image',
                    'Tags': [
                        {'Key': 'Stack', 'Value': 'autotrader-v2'},
                        {'Key': 'Env', 'Value': 'prod'},
                        {'Key': 'Purpose', 'Value': 'DR-backup'},
                        {'Key': 'RetainUntil', 'Value': (datetime.now().replace(day=datetime.now().day+7)).strftime('%Y-%m-%d')}
                    ]
                }
            ]
        )
        
        return response['ImageId']
    except Exception as e:
        print(f"Failed to create AMI: {e}")
        return None

def export_config_to_s3():
    """Export docker-compose.yml and env to S3"""
    s3 = boto3.client('s3')
    bucket = f'autotrader-backups-{datetime.now().strftime("%Y%m%d")}'
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    
    try:
        s3.create_bucket(Bucket=bucket)
        s3.put_bucket_tagging(
            Bucket=bucket,
            Tagging={
                'TagSet': [
                    {'Key': 'Stack', 'Value': 'autotrader-v2'},
                    {'Key': 'Env', 'Value': 'prod'},
                    {'Key': 'Purpose', 'Value': 'DR-backups'}
                ]
            }
        )
    except Exception as e:
        print(f"Bucket creation/tagging failed (may already exist): {e}")
    
    try:
        with open('/home/ubuntu/autotrader/docker-compose.yml', 'r') as f:
            s3.put_object(
                Bucket=bucket,
                Key=f'backups/{date_prefix}/docker-compose.yml',
                Body=f.read(),
                ServerSideEncryption='AES256'
            )
        
        with open('/home/ubuntu/autotrader/nginx/nginx.conf', 'r') as f:
            s3.put_object(
                Bucket=bucket,
                Key=f'backups/{date_prefix}/nginx.conf',
                Body=f.read(),
                ServerSideEncryption='AES256'
            )
        
        env_data = {
            "TRADING_MODE": os.getenv("TRADING_MODE", "paper"),
            "ENABLE_DEBUG": os.getenv("ENABLE_DEBUG", "false"),
            "REDIS_HOST": os.getenv("REDIS_HOST", "redis"),
            "REDIS_PORT": os.getenv("REDIS_PORT", "6379"),
            "backup_timestamp": datetime.now().isoformat()
        }
        
        s3.put_object(
            Bucket=bucket,
            Key=f'backups/{date_prefix}/env-config.json',
            Body=json.dumps(env_data, indent=2),
            ServerSideEncryption='AES256'
        )
        
        return f's3://{bucket}/backups/{date_prefix}/'
    except Exception as e:
        print(f"Failed to export config to S3: {e}")
        return None

if __name__ == "__main__":
    print("Creating DR backups...")
    
    ami_id = create_ami_snapshot()
    if ami_id:
        print(f"AMI Snapshot: {ami_id}")
    else:
        print("AMI Snapshot: FAILED")
    
    s3_path = export_config_to_s3()
    if s3_path:
        print(f"S3 Export: {s3_path}")
    else:
        print("S3 Export: FAILED")
    
    print("DR backup process completed")
