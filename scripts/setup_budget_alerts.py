#!/usr/bin/env python3
import boto3
import json

def create_budget_alerts():
    budgets = boto3.client('budgets', region_name='us-east-1')
    
    budget_config = {
        'BudgetName': 'AutoTrader-Monthly-Budget',
        'BudgetLimit': {
            'Amount': '100.00',
            'Unit': 'USD'
        },
        'TimeUnit': 'MONTHLY',
        'BudgetType': 'COST',
        'CostFilters': {
            'Service': ['Amazon Elastic Compute Cloud - Compute']
        }
    }
    
    sns = boto3.client('sns')
    topic_response = sns.create_topic(Name='AutoTraderBudgetAlerts')
    topic_arn = topic_response['TopicArn']
    
    try:
        budgets.create_budget(
            AccountId='123198875719',
            Budget=budget_config,
            NotificationsWithSubscribers=[
                {
                    'Notification': {
                        'NotificationType': 'ACTUAL',
                        'ComparisonOperator': 'GREATER_THAN',
                        'Threshold': 80.0,
                        'ThresholdType': 'PERCENTAGE'
                    },
                    'Subscribers': [
                        {
                            'SubscriptionType': 'SNS',
                            'Address': topic_arn
                        }
                    ]
                }
            ]
        )
        
        print(f"Budget created with SNS topic: {topic_arn}")
        return topic_arn
    except Exception as e:
        print(f"Failed to create budget: {e}")
        return None

if __name__ == "__main__":
    create_budget_alerts()
