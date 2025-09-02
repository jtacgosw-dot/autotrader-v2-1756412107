#!/usr/bin/env python3
import boto3
import json

def create_waf_rules():
    wafv2 = boto3.client('wafv2', region_name='us-east-1')
    
    web_acl_config = {
        'Name': 'AutoTraderWebACL',
        'Scope': 'CLOUDFRONT',
        'DefaultAction': {'Allow': {}},
        'Rules': [
            {
                'Name': 'ControllerEndpointRateLimit',
                'Priority': 1,
                'Statement': {
                    'RateBasedStatement': {
                        'Limit': 50,
                        'AggregateKeyType': 'IP',
                        'ScopeDownStatement': {
                            'OrStatement': {
                                'Statements': [
                                    {
                                        'ByteMatchStatement': {
                                            'SearchString': '/api/pause',
                                            'FieldToMatch': {'UriPath': {}},
                                            'TextTransformations': [
                                                {'Priority': 0, 'Type': 'LOWERCASE'}
                                            ],
                                            'PositionalConstraint': 'CONTAINS'
                                        }
                                    },
                                    {
                                        'ByteMatchStatement': {
                                            'SearchString': '/api/resume',
                                            'FieldToMatch': {'UriPath': {}},
                                            'TextTransformations': [
                                                {'Priority': 0, 'Type': 'LOWERCASE'}
                                            ],
                                            'PositionalConstraint': 'CONTAINS'
                                        }
                                    },
                                    {
                                        'ByteMatchStatement': {
                                            'SearchString': '/api/risk',
                                            'FieldToMatch': {'UriPath': {}},
                                            'TextTransformations': [
                                                {'Priority': 0, 'Type': 'LOWERCASE'}
                                            ],
                                            'PositionalConstraint': 'CONTAINS'
                                        }
                                    },
                                    {
                                        'ByteMatchStatement': {
                                            'SearchString': '/api/test/alert',
                                            'FieldToMatch': {'UriPath': {}},
                                            'TextTransformations': [
                                                {'Priority': 0, 'Type': 'LOWERCASE'}
                                            ],
                                            'PositionalConstraint': 'CONTAINS'
                                        }
                                    }
                                ]
                            }
                        }
                    }
                },
                'Action': {'Block': {}},
                'VisibilityConfig': {
                    'SampledRequestsEnabled': True,
                    'CloudWatchMetricsEnabled': True,
                    'MetricName': 'ControllerRateLimit'
                }
            },
            {
                'Name': 'AWSManagedRulesCommonRuleSet',
                'Priority': 2,
                'OverrideAction': {'None': {}},
                'Statement': {
                    'ManagedRuleGroupStatement': {
                        'VendorName': 'AWS',
                        'Name': 'AWSManagedRulesCommonRuleSet'
                    }
                },
                'VisibilityConfig': {
                    'SampledRequestsEnabled': True,
                    'CloudWatchMetricsEnabled': True,
                    'MetricName': 'CommonRuleSetMetric'
                }
            }
        ],
        'VisibilityConfig': {
            'SampledRequestsEnabled': True,
            'CloudWatchMetricsEnabled': True,
            'MetricName': 'AutoTraderWebACL'
        }
    }
    
    response = wafv2.create_web_acl(**web_acl_config)
    web_acl_arn = response['Summary']['ARN']
    
    cloudfront = boto3.client('cloudfront')
    distribution_id = 'E2Q821S151MNYL'
    
    dist_response = cloudfront.get_distribution_config(Id=distribution_id)
    config = dist_response['DistributionConfig']
    etag = dist_response['ETag']
    
    config['WebACLId'] = web_acl_arn
    
    cloudfront.update_distribution(
        Id=distribution_id,
        DistributionConfig=config,
        IfMatch=etag
    )
    
    print(f"WAF deployed with ARN: {web_acl_arn}")
    return web_acl_arn

if __name__ == "__main__":
    create_waf_rules()
