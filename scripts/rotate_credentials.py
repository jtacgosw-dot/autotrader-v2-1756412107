#!/usr/bin/env python3
import boto3
import secrets
import string
import json
from datetime import datetime

def generate_strong_password(length=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def rotate_credentials():
    secretsmanager = boto3.client('secretsmanager', region_name='us-east-1')
    
    new_viewer_password = generate_strong_password()
    viewer_secret = {
        "username": "viewer",
        "password": new_viewer_password,
        "role": "viewer",
        "rotated_at": datetime.utcnow().isoformat()
    }
    
    secretsmanager.update_secret(
        SecretId='autotrader/viewer-credentials',
        SecretString=json.dumps(viewer_secret)
    )
    
    new_controller_password = generate_strong_password()
    controller_secret = {
        "username": "controller",
        "password": new_controller_password,
        "role": "controller",
        "rotated_at": datetime.utcnow().isoformat()
    }
    
    secretsmanager.update_secret(
        SecretId='autotrader/controller-credentials',
        SecretString=json.dumps(controller_secret)
    )
    
    print("Credentials rotated successfully")
    print(f"New viewer password: {new_viewer_password}")
    print(f"New controller password: {new_controller_password}")
    
    return {
        "viewer_password": new_viewer_password,
        "controller_password": new_controller_password
    }

if __name__ == "__main__":
    rotate_credentials()
