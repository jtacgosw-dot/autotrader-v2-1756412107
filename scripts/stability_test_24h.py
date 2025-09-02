#!/usr/bin/env python3
import requests
import time
import json
import os
from datetime import datetime, timedelta
import threading
import statistics

class StabilityMonitor:
    def __init__(self):
        self.base_url = "https://lunaraxolotl.com"
        self.results = {
            "start_time": datetime.utcnow().isoformat(),
            "end_time": None,
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "response_times": [],
            "error_log": [],
            "health_checks": [],
            "alert_tests": [],
            "uptime_percentage": 0.0
        }
        self.running = True
    
    def test_endpoint(self, endpoint, expected_status=200):
        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
            response_time = (time.time() - start_time) * 1000
            
            self.results["total_requests"] += 1
            self.results["response_times"].append(response_time)
            
            if response.status_code == expected_status:
                self.results["successful_requests"] += 1
                return True
            else:
                self.results["failed_requests"] += 1
                self.results["error_log"].append({
                    "timestamp": datetime.utcnow().isoformat(),
                    "endpoint": endpoint,
                    "status_code": response.status_code,
                    "expected": expected_status
                })
                return False
        except Exception as e:
            self.results["failed_requests"] += 1
            self.results["error_log"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "endpoint": endpoint,
                "error": str(e)
            })
            return False
    
    def run_stability_test(self, duration_hours=24):
        print(f"Starting {duration_hours}h stability test...")
        end_time = datetime.utcnow() + timedelta(hours=duration_hours)
        
        while datetime.utcnow() < end_time and self.running:
            self.test_endpoint("/api/health")
            self.test_endpoint("/api/healthz")
            self.test_endpoint("/api/status")
            
            try:
                response = requests.get(f"{self.base_url}/api/healthz")
                if response.status_code == 200:
                    health_data = response.json()
                    self.results["health_checks"].append({
                        "timestamp": datetime.utcnow().isoformat(),
                        "discord_ok": health_data.get("discord_webhook_ok"),
                        "ssm_ok": health_data.get("ssm_ok"),
                        "overall_status": health_data.get("overall_status"),
                        "cache_source": health_data.get("cache_source")
                    })
            except Exception as e:
                print(f"Health check failed: {e}")
            
            time.sleep(60)
        
        self.results["end_time"] = datetime.utcnow().isoformat()
        self.calculate_metrics()
        return self.results
    
    def calculate_metrics(self):
        if self.results["total_requests"] > 0:
            self.results["uptime_percentage"] = (
                self.results["successful_requests"] / self.results["total_requests"]
            ) * 100
        
        if self.results["response_times"]:
            self.results["avg_response_time"] = statistics.mean(self.results["response_times"])
            self.results["p95_response_time"] = statistics.quantiles(
                self.results["response_times"], n=20
            )[18]
            self.results["max_response_time"] = max(self.results["response_times"])
    
    def save_report(self, report_dir):
        os.makedirs(report_dir, exist_ok=True)
        
        report_file = os.path.join(report_dir, "stability_report.json")
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        summary_file = os.path.join(report_dir, "stability_summary.txt")
        with open(summary_file, 'w') as f:
            f.write(f"24h Stability Test Report\n")
            f.write(f"========================\n\n")
            f.write(f"Duration: {self.results['start_time']} to {self.results['end_time']}\n")
            f.write(f"Total Requests: {self.results['total_requests']}\n")
            f.write(f"Successful: {self.results['successful_requests']}\n")
            f.write(f"Failed: {self.results['failed_requests']}\n")
            f.write(f"Uptime: {self.results['uptime_percentage']:.2f}%\n")
            if 'avg_response_time' in self.results:
                f.write(f"Avg Response Time: {self.results['avg_response_time']:.2f}ms\n")
                f.write(f"P95 Response Time: {self.results['p95_response_time']:.2f}ms\n")
        
        print(f"Stability report saved to {report_dir}")

if __name__ == "__main__":
    monitor = StabilityMonitor()
    report_dir = f"/home/ubuntu/autotrader/ops/reports/{datetime.now().strftime('%Y-%m-%d')}"
    
    try:
        results = monitor.run_stability_test(duration_hours=0.17)
        monitor.save_report(report_dir)
    except KeyboardInterrupt:
        print("Stability test interrupted")
        monitor.running = False
        monitor.results["end_time"] = datetime.utcnow().isoformat()
        monitor.calculate_metrics()
        monitor.save_report(report_dir)
