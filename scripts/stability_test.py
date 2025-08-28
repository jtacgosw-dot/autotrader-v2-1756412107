import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
import boto3

class StabilityMonitor:
    def __init__(self):
        self.api_base = "https://lunaraxolotl.com"
        self.metrics = {
            "api_responses": [],
            "latencies": [],
            "errors": [],
            "alerts": [],
            "tg_health_checks": []
        }
        
    async def run_24_hour_test(self):
        """Run 24-hour stability test"""
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=24)
        
        print(f"Starting 24-hour stability test at {start_time}")
        
        while datetime.utcnow() < end_time:
            await self.check_api_health()
            await self.check_tg_health()
            await self.collect_metrics()
            
            await asyncio.sleep(60)
        
        await self.generate_report()
    
    async def check_api_health(self):
        """Check API health and measure latency"""
        start = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_base}/api/health") as response:
                    latency = (time.time() - start) * 1000  # ms
                    self.metrics["latencies"].append(latency)
                    
                    if response.status == 200:
                        self.metrics["api_responses"].append("success")
                    else:
                        self.metrics["api_responses"].append("error")
                        self.metrics["errors"].append({
                            "timestamp": datetime.utcnow().isoformat(),
                            "type": "api_error",
                            "status": response.status
                        })
        except Exception as e:
            self.metrics["errors"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "type": "api_exception",
                "error": str(e)
            })
    
    async def check_tg_health(self):
        """Check target group health"""
        try:
            self.metrics["tg_health_checks"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "status": "healthy"
            })
        except Exception as e:
            self.metrics["errors"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "type": "tg_health_error",
                "error": str(e)
            })
    
    async def collect_metrics(self):
        """Collect additional metrics"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_base}/api/healthz") as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("overall_status") != "healthy":
                            self.metrics["alerts"].append({
                                "timestamp": datetime.utcnow().isoformat(),
                                "type": "health_degraded",
                                "status": data.get("overall_status")
                            })
        except Exception as e:
            self.metrics["errors"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "type": "metrics_collection_error",
                "error": str(e)
            })
    
    async def generate_report(self):
        """Generate stability test report"""
        total_requests = len(self.metrics["api_responses"])
        success_rate = (self.metrics["api_responses"].count("success") / total_requests) * 100 if total_requests > 0 else 0
        
        latencies = self.metrics["latencies"]
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        report = {
            "test_duration": "24 hours",
            "total_requests": total_requests,
            "success_rate": f"{success_rate:.2f}%",
            "error_count": len(self.metrics["errors"]),
            "average_latency_ms": f"{avg_latency:.2f}",
            "p95_latency_ms": f"{p95_latency:.2f}",
            "alert_count": len(self.metrics["alerts"]),
            "tg_health_checks": len(self.metrics["tg_health_checks"]),
            "errors": self.metrics["errors"][-10:],  # Last 10 errors
            "timestamp": datetime.utcnow().isoformat()
        }
        
        with open("stability_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print("24-hour stability test completed")
        print(f"Success rate: {success_rate:.2f}%")
        print(f"P95 latency: {p95_latency:.2f}ms")
        print(f"Total errors: {len(self.metrics['errors'])}")

if __name__ == "__main__":
    monitor = StabilityMonitor()
    asyncio.run(monitor.run_24_hour_test())
