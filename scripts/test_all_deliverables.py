#!/usr/bin/env python3
import requests
import json
import subprocess
import os
from datetime import datetime

def test_debug_endpoints():
    """Test debug endpoints with ENABLE_DEBUG=false"""
    print("=== Testing Debug Endpoints ===")
    
    response = requests.get('https://lunaraxolotl.com/api/debug/whoami')
    print(f"Debug whoami (no auth): {response.status_code}")
    
    response = requests.get('https://lunaraxolotl.com/api/debug/cors')
    print(f"Debug cors (no auth): {response.status_code}")
    
    return response.status_code == 404

def test_redis_health_cache():
    """Test Redis health cache consistency"""
    print("=== Testing Redis Health Cache ===")
    
    responses = []
    for i in range(5):
        response = requests.get('https://lunaraxolotl.com/api/healthz')
        if response.status_code == 200:
            data = response.json()
            responses.append({
                'discord_webhook_ok': data.get('discord_webhook_ok'),
                'ssm_ok': data.get('ssm_ok'),
                'cache_source': data.get('cache_source')
            })
    
    if responses:
        first = responses[0]
        consistent = all(r == first for r in responses)
        print(f"Health cache consistency: {consistent}")
        print(f"Sample response: {first}")
        return consistent
    
    return False

def test_smoke_trade_endpoint():
    """Test smoke trade endpoint access control"""
    print("=== Testing Smoke Trade Endpoint ===")
    
    response = requests.post('https://lunaraxolotl.com/api/test/smoke_trade', 
                           json={'symbol': 'BTC/USDT', 'side': 'buy', 'notionalUsd': 5})
    print(f"Smoke trade (no auth): {response.status_code}")
    
    return response.status_code in [401, 403]

def test_csp_headers():
    """Test CSP headers"""
    print("=== Testing CSP Headers ===")
    
    response = requests.get('https://app.lunaraxolotl.com/')
    csp_header = response.headers.get('content-security-policy', '')
    
    has_unsafe_inline = 'unsafe-inline' in csp_header
    print(f"CSP header present: {bool(csp_header)}")
    print(f"Contains unsafe-inline: {has_unsafe_inline}")
    
    return bool(csp_header) and not has_unsafe_inline

def test_risk_settings():
    """Test conservative risk settings"""
    print("=== Testing Risk Settings ===")
    
    response = requests.get('https://lunaraxolotl.com/api/risk')
    if response.status_code == 200:
        data = response.json()
        conservative = (
            data.get('daily_kill_pct') == 0.8 and
            data.get('max_pos_pct') == 0.5 and
            data.get('max_slippage_bps') == 6 and
            data.get('withdrawals_enabled') == False
        )
        print(f"Conservative risk settings: {conservative}")
        print(f"Settings: {data}")
        return conservative
    
    return False

def test_trading_mode():
    """Test trading mode endpoint"""
    print("=== Testing Trading Mode ===")
    
    response = requests.get('https://lunaraxolotl.com/api/mode')
    if response.status_code == 200:
        data = response.json()
        is_paper = data.get('mode') == 'paper'
        print(f"Trading mode is paper: {is_paper}")
        print(f"Mode data: {data}")
        return is_paper
    
    return False

def test_maintenance_mode():
    """Test maintenance mode"""
    print("=== Testing Maintenance Mode ===")
    
    response = requests.get('https://lunaraxolotl.com/api/maintenance')
    if response.status_code == 200:
        data = response.json()
        print(f"Maintenance mode: {data}")
        return 'maintenance_mode' in data
    
    return False

def run_all_tests():
    """Run all deliverable tests"""
    print(f"AutoTrader Deliverables Test Suite - {datetime.now()}")
    print("=" * 60)
    
    results = {
        'debug_endpoints': test_debug_endpoints(),
        'redis_health_cache': test_redis_health_cache(),
        'smoke_trade_endpoint': test_smoke_trade_endpoint(),
        'csp_headers': test_csp_headers(),
        'risk_settings': test_risk_settings(),
        'trading_mode': test_trading_mode(),
        'maintenance_mode': test_maintenance_mode()
    }
    
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY:")
    for test, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{test:20} : {status}")
    
    total_tests = len(results)
    passed_tests = sum(results.values())
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    return results

if __name__ == "__main__":
    results = run_all_tests()
    
    with open('/home/ubuntu/autotrader/ops/reports/2025-09-02/deliverables_test_results.json', 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'summary': {
                'total_tests': len(results),
                'passed_tests': sum(results.values()),
                'success_rate': sum(results.values()) / len(results)
            }
        }, f, indent=2)
    
    print(f"\nResults saved to ops/reports/2025-09-02/deliverables_test_results.json")
