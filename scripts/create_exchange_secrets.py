#!/usr/bin/env python3
import boto3
import json
from datetime import datetime

def create_exchange_secrets():
    """Create placeholder exchange secrets in Secrets Manager"""
    secrets_client = boto3.client('secretsmanager')
    
    binance_secret = {
        "apiKey": "PLACEHOLDER_BINANCE_API_KEY",
        "secret": "PLACEHOLDER_BINANCE_SECRET",
        "recvWindow": 5000,
        "trading": False,
        "withdrawals": False
    }
    
    kucoin_secret = {
        "apiKey": "PLACEHOLDER_KUCOIN_API_KEY", 
        "secret": "PLACEHOLDER_KUCOIN_SECRET",
        "passphrase": "PLACEHOLDER_KUCOIN_PASSPHRASE",
        "trading": False,
        "withdrawals": False
    }
    
    try:
        binance_response = secrets_client.create_secret(
            Name='autotrader/binance',
            Description='Binance API credentials for AutoTrader',
            SecretString=json.dumps(binance_secret),
            Tags=[
                {'Key': 'Stack', 'Value': 'autotrader-v2'},
                {'Key': 'Env', 'Value': 'prod'},
                {'Key': 'Purpose', 'Value': 'exchange-api'}
            ]
        )
        print(f"Binance secret created: {binance_response['ARN']}")
        
    except secrets_client.exceptions.ResourceExistsException:
        print("Binance secret already exists")
        binance_response = secrets_client.describe_secret(SecretId='autotrader/binance')
    
    try:
        kucoin_response = secrets_client.create_secret(
            Name='autotrader/kucoin',
            Description='KuCoin API credentials for AutoTrader', 
            SecretString=json.dumps(kucoin_secret),
            Tags=[
                {'Key': 'Stack', 'Value': 'autotrader-v2'},
                {'Key': 'Env', 'Value': 'prod'},
                {'Key': 'Purpose', 'Value': 'exchange-api'}
            ]
        )
        print(f"KuCoin secret created: {kucoin_response['ARN']}")
        
    except secrets_client.exceptions.ResourceExistsException:
        print("KuCoin secret already exists")
        kucoin_response = secrets_client.describe_secret(SecretId='autotrader/kucoin')
    
    return {
        'binance_arn': binance_response['ARN'],
        'kucoin_arn': kucoin_response['ARN']
    }

if __name__ == "__main__":
    print("Creating exchange secrets...")
    result = create_exchange_secrets()
    print(f"Exchange secrets created successfully:")
    print(f"Binance ARN: {result['binance_arn']}")
    print(f"KuCoin ARN: {result['kucoin_arn']}")
