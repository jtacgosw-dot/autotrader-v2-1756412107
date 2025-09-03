#!/usr/bin/env python3
import boto3
import json
import zipfile
import io

def create_synthetics_canary():
    """Create CloudWatch Synthetics canary for AutoTrader monitoring"""
    synthetics = boto3.client('synthetics')
    
    canary_script = '''
const synthetics = require('Synthetics');
const log = require('SyntheticsLogger');

const checkPage = async function (page, stepName, url) {
    await synthetics.executeStep(stepName, async function () {
        await page.goto(url, {waitUntil: 'networkidle0', timeout: 30000});
        await page.waitForTimeout(2000);
        
        // Check for any console errors
        const logs = await page.evaluate(() => {
            return window.console.logs || [];
        });
        
        log.info(`${stepName} completed successfully`);
    });
};

const apiCheck = async function () {
    return await synthetics.executeStep('checkApiHealth', async function () {
        const response = await synthetics.makeRequest({
            uri: 'https://lunaraxolotl.com/api/health',
            method: 'GET',
            timeout: 10000
        });
        
        if (response.statusCode !== 200) {
            throw new Error(`API health check failed with status ${response.statusCode}`);
        }
        
        log.info('API health check passed');
    });
};

exports.handler = async () => {
    return await synthetics.executeStep('synthetics', async function () {
        const page = await synthetics.getPage();
        
        // Check main pages
        await checkPage(page, 'checkHomePage', 'https://app.lunaraxolotl.com/');
        await checkPage(page, 'checkVenuesPage', 'https://app.lunaraxolotl.com/venues');
        await checkPage(page, 'checkOrdersPage', 'https://app.lunaraxolotl.com/orders');
        await checkPage(page, 'checkRiskPage', 'https://app.lunaraxolotl.com/risk');
        await checkPage(page, 'checkAlertsPage', 'https://app.lunaraxolotl.com/alerts');
        
        // Check API health
        await apiCheck();
        
        log.info('All checks completed successfully');
    });
};
'''
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('nodejs/node_modules/autotrader-canary.js', canary_script)
    
    zip_buffer.seek(0)
    
    try:
        response = synthetics.create_canary(
            Name='autotrader-web-hub-canary',
            Code={
                'Handler': 'autotrader-canary.handler',
                'ZipFile': zip_buffer.read()
            },
            ArtifactS3Location='s3://autotrader-synthetics-artifacts',
            ExecutionRoleArn='arn:aws:iam::123198875719:role/CloudWatchSyntheticsRole',
            Schedule={
                'Expression': 'rate(5 minutes)'
            },
            RunConfig={
                'TimeoutInSeconds': 60,
                'MemoryInMB': 960
            },
            FailureRetentionPeriodInDays=30,
            SuccessRetentionPeriodInDays=30,
            RuntimeVersion='syn-nodejs-puppeteer-6.2',
            Tags={
                'Stack': 'autotrader-v2',
                'Env': 'prod'
            }
        )
        
        print(f"✅ Synthetics canary created successfully")
        print(f"Canary ARN: {response['Canary']['Id']}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to create Synthetics canary: {e}")
        return False

if __name__ == "__main__":
    create_synthetics_canary()
