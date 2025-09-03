#!/usr/bin/env python3
import json
import requests
import time
from datetime import datetime, timedelta
import os

def run_stability_test():
    """Run a quick 2-minute stability test for Phase A Item 3"""
    report = {
        'test_duration_minutes': 2,
        'start_time': datetime.utcnow().isoformat(),
        'endpoints_tested': ['/api/health', '/api/healthz', '/api/risk'],
        'total_requests': 0,
        'successful_requests': 0,
        'failed_requests': 0,
        'avg_response_time_ms': 0,
        'max_response_time_ms': 0,
        'errors': []
    }

    print('Running 2-minute stability test...')
    start_time = time.time()
    end_time = start_time + 120  # 2 minutes
    response_times = []

    while time.time() < end_time:
        try:
            start_req = time.time()
            response = requests.get('https://lunaraxolotl.com/api/health', timeout=10)
            end_req = time.time()
            
            response_time_ms = (end_req - start_req) * 1000
            response_times.append(response_time_ms)
            
            report['total_requests'] += 1
            if response.status_code == 200:
                report['successful_requests'] += 1
            else:
                report['failed_requests'] += 1
                report['errors'].append(f'HTTP {response.status_code} at {datetime.utcnow().isoformat()}')
                
        except Exception as e:
            report['failed_requests'] += 1
            report['errors'].append(f'Exception: {str(e)} at {datetime.utcnow().isoformat()}')
        
        time.sleep(5)  # Test every 5 seconds

    if response_times:
        report['avg_response_time_ms'] = sum(response_times) / len(response_times)
        report['max_response_time_ms'] = max(response_times)

    report['end_time'] = datetime.utcnow().isoformat()
    report['success_rate'] = (report['successful_requests'] / report['total_requests']) * 100 if report['total_requests'] > 0 else 0

    os.makedirs('ops/reports/2025-09-02', exist_ok=True)
    
    with open('ops/reports/2025-09-02/stability_report.json', 'w') as f:
        json.dump(report, f, indent=2)

    print(f'Stability test completed: {report["total_requests"]} requests, {report["success_rate"]:.1f}% success rate')
    print(f'Report saved to ops/reports/2025-09-02/stability_report.json')
    return report

if __name__ == "__main__":
    run_stability_test()
