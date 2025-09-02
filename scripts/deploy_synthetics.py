#!/usr/bin/env python3
import boto3
import json
import zipfile
import io

def create_synthetics_canary():
    synthetics = boto3.client('synthetics', region_name='us-east-1')
    
    canary_script = '''
const synthetics = require('Synthetics');
const log = require('SyntheticsLogger');

const checkWebHub = async function () {
    const page = await synthetics.getPage();
    
    const urls = [
        'https://app.lunaraxolotl.com/',
        'https://app.lunaraxolotl.com/venues',
        'https://app.lunaraxolotl.com/orders',
        'https://app.lunaraxolotl.com/risk',
        'https://app.lunaraxolotl.com/alerts'
    ];
    
    for (const url of urls) {
        const response = await page.goto(url, {waitUntil: 'networkidle0'});
        if (!response.ok()) {
            throw new Error(`Failed to load ${url}: ${response.status()}`);
        }
        log.info(`Successfully loaded ${url}`);
    }
    
    const apiResponse = await page.goto('https://lunaraxolotl.com/api/healthz');
    if (!apiResponse.ok()) {
        throw new Error(`API health check failed: ${apiResponse.status()}`);
    }
    
    const healthData = await apiResponse.json();
    if (healthData.overall_status !== 'healthy') {
        throw new Error(`API health status: ${healthData.overall_status}`);
    }
    
    log.info('All health checks passed');
};

exports.handler = async () => {
    return await synthetics.executeStep('checkWebHub', checkWebHub);
};
'''
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
        zip_file.writestr('nodejs/node_modules/autotrader-canary.js', canary_script)
    
    s3 = boto3.client('s3')
    bucket_name = 'autotrader-synthetics-artifacts'
    
    try:
        s3.create_bucket(Bucket=bucket_name)
    except:
        pass
    
    s3.put_object(
        Bucket=bucket_name,
        Key='canary-script.zip',
        Body=zip_buffer.getvalue()
    )
    
    try:
        canary_response = synthetics.create_canary(
            Name='autotrader-web-hub-canary',
            Code={
                'S3Bucket': bucket_name,
                'S3Key': 'canary-script.zip',
                'Handler': 'autotrader-canary.handler'
            },
            ExecutionRoleArn='arn:aws:iam::123198875719:role/CloudWatchSyntheticsRole',
            Schedule={
                'Expression': 'rate(5 minutes)'
            },
            RunConfig={
                'TimeoutInSeconds': 60
            },
            ArtifactS3Location=f's3://{bucket_name}/canary-artifacts/',
            RuntimeVersion='syn-nodejs-puppeteer-6.2',
            SuccessRetentionPeriodInDays=30,
            FailureRetentionPeriodInDays=30
        )
        
        print(f"Created canary: {canary_response['Canary']['Name']}")
        return canary_response['Canary']['Name']
    except Exception as e:
        print(f"Failed to create canary: {e}")
        return None

if __name__ == "__main__":
    create_synthetics_canary()
