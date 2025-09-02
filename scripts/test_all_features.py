#!/usr/bin/env python3
import requests
import subprocess
import json
import time
from datetime import datetime

def test_debug_endpoints():
    """Test debug endpoint feature flags"""
    print("=== Testing Debug Endpoints ===")
    
    response = requests.get("https://lunaraxolotl.com/api/debug/whoami")
    print(f"Debug whoami (disabled): {response.status_code}")
    
    response = requests.get("https://lunaraxolotl.com/api/debug/cors")
    print(f"Debug CORS (disabled): {response.status_code}")
    
    return response.status_code == 404

def test_redis_health_cache():
    """Test Redis health cache consistency"""
    print("=== Testing Redis Health Cache ===")
    
    responses = []
    for i in range(5):
        response = requests.get("https://lunaraxolotl.com/api/healthz")
        if response.status_code == 200:
            data = response.json()
            responses.append({
                "discord_ok": data.get("discord_webhook_ok"),
                "ssm_ok": data.get("ssm_ok"),
                "cache_source": data.get("cache_source")
            })
        time.sleep(1)
    
    consistent = all(r["discord_ok"] == responses[0]["discord_ok"] for r in responses)
    print(f"Health cache consistency: {consistent}")
    print(f"Cache source: {responses[0].get('cache_source')}")
    
    return consistent

def test_csp_headers():
    """Test CSP implementation"""
    print("=== Testing CSP Headers ===")
    
    response = requests.get("https://app.lunaraxolotl.com/")
    csp_header = response.headers.get("Content-Security-Policy")
    print(f"CSP Header present: {csp_header is not None}")
    if csp_header:
        print(f"CSP: {csp_header[:100]}...")
    
    return csp_header is not None

def run_all_tests():
    """Run all feature tests"""
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "debug_endpoints": test_debug_endpoints(),
        "redis_cache": test_redis_health_cache(),
        "csp_headers": test_csp_headers()
    }
    
    with open("/home/ubuntu/autotrader/ops/reports/test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n=== Test Results ===")
    for test, result in results.items():
        if test != "timestamp":
            print(f"{test}: {'✅ PASS' if result else '❌ FAIL'}")
    
    return results

if __name__ == "__main__":
    run_all_tests()
