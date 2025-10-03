const synthetics = require('Synthetics');
const log = require('SyntheticsLogger');

const apiCanaryBlueprint = async function () {
    const urls = [
        'https://app.lunaraxolotl.com/',
        'https://app.lunaraxolotl.com/login',
        'https://lunaraxolotl.com/api/healthz',
    ];

    const headers = {
        'User-Agent': 'CloudWatch-Synthetics-Canary'
    };

    for (const url of urls) {
        let page = await synthetics.getPage();
        
        try {
            const response = await page.goto(url, {
                waitUntil: 'networkidle0',
                timeout: 30000
            });

            if (!response) {
                throw new Error(`Failed to load ${url}`);
            }

            const status = response.status();
            log.info(`URL: ${url} | Status: ${status}`);

            if (status < 200 || status >= 400) {
                throw new Error(`Failed response: ${status} for ${url}`);
            }

            await synthetics.takeScreenshot(url.replace(/[^a-zA-Z0-9]/g, '_'), 'loaded');

        } catch (error) {
            log.error(`Error loading ${url}: ${error.message}`);
            throw error;
        }
    }

    let page = await synthetics.getPage();
    await page.goto('https://app.lunaraxolotl.com/login', {
        waitUntil: 'networkidle0',
        timeout: 30000
    });

    const username = process.env.CANARY_USERNAME || 'viewer';
    const password = process.env.CANARY_PASSWORD;
    
    if (!password) {
        throw new Error('CANARY_PASSWORD environment variable is required');
    }
    
    await page.type('input[id="username"]', username);
    await page.type('input[id="password"]', password);
    await page.click('button[type="submit"]');

    await page.waitForNavigation({ waitUntil: 'networkidle0' });

    await page.click('text=Live Feed');
    await page.waitForTimeout(5000);

    const connected = await page.$('text=Connected');
    if (!connected) {
        throw new Error('SSE connection not established on Live Feed page');
    }

    log.info('SSE connection successful');
    await synthetics.takeScreenshot('live_feed', 'connected');
};

exports.handler = async () => {
    return await apiCanaryBlueprint();
};
