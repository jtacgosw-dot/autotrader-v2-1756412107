#!/usr/bin/env python3
"""
24-hour stability monitoring script for AutoTrader production stack.
Collects metrics on API health, latency, errors, and system components.
"""

import asyncio
import aiohttp
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import statistics

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stability_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class StabilityMonitor:
    def __init__(self, api_base: str = "https://lunaraxolotl.com"):
        self.api_base = api_base
        self.metrics = {
            "api_responses": [],
            "latencies": [],
            "errors": [],
            "health_checks": [],
            "tg_health_checks": [],
            "start_time": None,
            "end_time": None
        }
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_api_health(self) -> Dict[str, Any]:
        """Check API health and measure response time"""
        start_time = time.time()
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "/api/health",
            "success": False,
            "latency_ms": 0,
            "status_code": None,
            "error": None
        }
        
        try:
            if not self.session:
                raise RuntimeError("Session not initialized")
            async with self.session.get(f"{self.api_base}/api/health") as response:
                latency = (time.time() - start_time) * 1000
                result.update({
                    "success": response.status == 200,
                    "latency_ms": round(latency, 2),
                    "status_code": response.status
                })
                
                if response.status == 200:
                    self.metrics["api_responses"].append("success")
                    self.metrics["latencies"].append(latency)
                else:
                    self.metrics["api_responses"].append("error")
                    result["error"] = f"HTTP {response.status}"
                    
        except Exception as e:
            result["error"] = str(e)
            self.metrics["api_responses"].append("exception")
            logger.error(f"API health check failed: {e}")
        
        return result
    
    async def check_health_aggregator(self) -> Dict[str, Any]:
        """Check the /api/healthz aggregator endpoint"""
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": "/api/healthz",
            "success": False,
            "components": {},
            "overall_status": "unknown",
            "error": None
        }
        
        try:
            if not self.session:
                raise RuntimeError("Session not initialized")
            async with self.session.get(f"{self.api_base}/api/healthz") as response:
                if response.status == 200:
                    data = await response.json()
                    result.update({
                        "success": True,
                        "components": {
                            "api_ok": data.get("api_ok", False),
                            "nginx_ok": data.get("nginx_ok", False),
                            "tg_healthy": data.get("tg_healthy", False),
                            "ssm_ok": data.get("ssm_ok", False),
                            "discord_webhook_ok": data.get("discord_webhook_ok", False)
                        },
                        "overall_status": data.get("overall_status", "unknown")
                    })
                    self.metrics["health_checks"].append(result)
                else:
                    result["error"] = f"HTTP {response.status}"
                    
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Health aggregator check failed: {e}")
        
        return result
    
    async def run_stability_test(self, duration_hours: float = 24.0):
        """Run the stability test for specified duration"""
        logger.info(f"Starting {duration_hours}-hour stability test")
        self.metrics["start_time"] = datetime.utcnow().isoformat()
        
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=duration_hours)
        
        check_interval = 60  # Check every minute
        check_count = 0
        
        while datetime.utcnow() < end_time:
            check_count += 1
            logger.info(f"Running check #{check_count}")
            
            api_result = await self.check_api_health()
            health_result = await self.check_health_aggregator()
            
            if api_result.get("error"):
                self.metrics["errors"].append(api_result)
            if health_result.get("error"):
                self.metrics["errors"].append(health_result)
            
            await asyncio.sleep(check_interval)
            
            if check_count % 10 == 0:
                elapsed = datetime.utcnow() - start_time
                remaining = end_time - datetime.utcnow()
                logger.info(f"Progress: {elapsed} elapsed, {remaining} remaining")
        
        self.metrics["end_time"] = datetime.utcnow().isoformat()
        logger.info("Stability test completed")
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive stability test report"""
        total_requests = len(self.metrics["api_responses"])
        success_count = self.metrics["api_responses"].count("success")
        error_count = self.metrics["api_responses"].count("error")
        exception_count = self.metrics["api_responses"].count("exception")
        
        success_rate = (success_count / total_requests * 100) if total_requests > 0 else 0
        
        latencies = self.metrics["latencies"]
        latency_stats = {}
        if latencies:
            latency_stats = {
                "min_ms": round(min(latencies), 2),
                "max_ms": round(max(latencies), 2),
                "avg_ms": round(statistics.mean(latencies), 2),
                "p50_ms": round(statistics.median(latencies), 2),
                "p95_ms": round(statistics.quantiles(latencies, n=20)[18], 2) if len(latencies) >= 20 else round(max(latencies), 2),
                "p99_ms": round(statistics.quantiles(latencies, n=100)[98], 2) if len(latencies) >= 100 else round(max(latencies), 2)
            }
        
        health_summary = {"total_checks": len(self.metrics["health_checks"])}
        if self.metrics["health_checks"]:
            component_stats = {}
            for component in ["api_ok", "nginx_ok", "tg_healthy", "ssm_ok", "discord_webhook_ok"]:
                component_values = [check["components"].get(component, False) for check in self.metrics["health_checks"]]
                component_stats[component] = {
                    "success_rate": (sum(component_values) / len(component_values) * 100) if component_values else 0,
                    "total_checks": len(component_values)
                }
            health_summary["components"] = component_stats
        
        report = {
            "test_summary": {
                "start_time": self.metrics["start_time"],
                "end_time": self.metrics["end_time"],
                "duration_hours": 24.0,
                "total_api_requests": total_requests,
                "success_rate_percent": round(success_rate, 2)
            },
            "api_performance": {
                "success_count": success_count,
                "error_count": error_count,
                "exception_count": exception_count,
                "latency_statistics": latency_stats
            },
            "health_monitoring": health_summary,
            "error_summary": {
                "total_errors": len(self.metrics["errors"]),
                "recent_errors": self.metrics["errors"][-10:] if self.metrics["errors"] else []
            },
            "recommendations": self._generate_recommendations(success_rate, latency_stats, health_summary)
        }
        
        return report
    
    def _generate_recommendations(self, success_rate: float, latency_stats: Dict, health_summary: Dict) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        if success_rate < 99.0:
            recommendations.append(f"API success rate ({success_rate:.2f}%) is below 99% - investigate error causes")
        
        if latency_stats.get("p95_ms", 0) > 1000:
            recommendations.append(f"P95 latency ({latency_stats['p95_ms']}ms) exceeds 1000ms - consider performance optimization")
        
        if latency_stats.get("avg_ms", 0) > 500:
            recommendations.append(f"Average latency ({latency_stats['avg_ms']}ms) exceeds 500ms - review API performance")
        
        components = health_summary.get("components", {})
        for component, stats in components.items():
            if stats.get("success_rate", 0) < 95:
                recommendations.append(f"{component} health check success rate ({stats['success_rate']:.1f}%) is below 95%")
        
        if not recommendations:
            recommendations.append("System stability looks good - all metrics within acceptable ranges")
        
        return recommendations
    
    async def run_short_test(self, duration_minutes: int = 5):
        """Run a shorter test for demonstration purposes"""
        logger.info(f"Starting {duration_minutes}-minute stability test")
        self.metrics["start_time"] = datetime.utcnow().isoformat()
        
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        check_interval = 10  # Check every 10 seconds for demo
        check_count = 0
        
        while datetime.utcnow() < end_time:
            check_count += 1
            logger.info(f"Running check #{check_count}")
            
            api_result = await self.check_api_health()
            health_result = await self.check_health_aggregator()
            
            if api_result.get("error"):
                self.metrics["errors"].append(api_result)
            if health_result.get("error"):
                self.metrics["errors"].append(health_result)
            
            await asyncio.sleep(check_interval)
        
        self.metrics["end_time"] = datetime.utcnow().isoformat()
        logger.info("Short stability test completed")

async def main():
    """Main function to run stability test"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AutoTrader Stability Monitor")
    parser.add_argument("--duration", type=float, default=24.0, help="Test duration in hours")
    parser.add_argument("--short", action="store_true", help="Run 5-minute demo test")
    parser.add_argument("--api-base", default="https://lunaraxolotl.com", help="API base URL")
    parser.add_argument("--output", default="stability_report.json", help="Output report file")
    
    args = parser.parse_args()
    
    async with StabilityMonitor(args.api_base) as monitor:
        try:
            if args.short:
                await monitor.run_short_test(5)
            else:
                await monitor.run_stability_test(args.duration)
            
            report = monitor.generate_report()
            
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Report saved to {args.output}")
            
            print("\n" + "="*60)
            print("STABILITY TEST SUMMARY")
            print("="*60)
            print(f"Duration: {args.duration if not args.short else 0.083:.1f} hours")
            print(f"Total API Requests: {report['test_summary']['total_api_requests']}")
            print(f"Success Rate: {report['test_summary']['success_rate_percent']:.2f}%")
            
            if report['api_performance']['latency_statistics']:
                stats = report['api_performance']['latency_statistics']
                print(f"Average Latency: {stats['avg_ms']:.2f}ms")
                print(f"P95 Latency: {stats['p95_ms']:.2f}ms")
            
            print(f"Total Errors: {report['error_summary']['total_errors']}")
            
            print("\nRecommendations:")
            for rec in report['recommendations']:
                print(f"- {rec}")
            
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        except Exception as e:
            logger.error(f"Test failed: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())
