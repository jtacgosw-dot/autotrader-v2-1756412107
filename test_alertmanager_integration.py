#!/usr/bin/env python3
"""
Integration test for AlertManager
Tests deduplication, incident lifecycle, and Discord integration
"""
import asyncio
import redis
import time
from alerts.manager import AlertManager

WEBHOOK_URL = "https://discord.com/api/webhooks/1410739080538624121/oK9zdW5B18b2MhGJJMcLo-hojL3uB4xukMPk8PMlbhCocPxLgAJIGpuMc4eaMyCWza-X"

async def test_basic_alert():
    """Test basic alert sending"""
    print("\n🧪 Test 1: Basic Alert Sending")
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    am = AlertManager(r, WEBHOOK_URL)
    
    await am.send(
        type="test",
        severity="info",
        key="test-1",
        title="✅ AlertManager Integration Test",
        body="Testing basic alert functionality",
        tags={"test": "integration", "version": "1.0"}
    )
    print("✅ Basic alert sent successfully")
    await asyncio.sleep(2)

async def test_deduplication():
    """Test deduplication - same key should update, not create new"""
    print("\n🧪 Test 2: Deduplication & Message Editing")
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    am = AlertManager(r, WEBHOOK_URL)
    
    print("  → Sending first alert (should create new message)...")
    await am.send(
        type="health",
        severity="warning",
        key="dedup-test",
        title="⚠️ Deduplication Test",
        body="First occurrence",
        tags={"occurrence": "1"}
    )
    await asyncio.sleep(3)
    
    print("  → Sending second alert (should update existing message if cooldown passed)...")
    await am.send(
        type="health",
        severity="warning",
        key="dedup-test",
        title="⚠️ Deduplication Test",
        body="Second occurrence - this should update the same message",
        tags={"occurrence": "2"}
    )
    await asyncio.sleep(3)
    
    print("✅ Deduplication test completed - check Discord for message updates")

async def test_incident_lifecycle():
    """Test full incident lifecycle: open -> update -> resolve"""
    print("\n🧪 Test 3: Incident Lifecycle")
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    am = AlertManager(r, WEBHOOK_URL)
    
    incident_key = f"lifecycle-{int(time.time())}"
    
    print("  → Opening incident...")
    await am.send(
        type="infra",
        severity="critical",
        key=incident_key,
        title="🚨 CRITICAL: Service Down",
        body="API service is not responding",
        tags={"service": "api", "status": "down"}
    )
    await asyncio.sleep(3)
    
    print("  → Updating incident...")
    await am.send(
        type="infra",
        severity="critical",
        key=incident_key,
        title="🚨 CRITICAL: Service Down",
        body="API service still down - 2nd check failed",
        tags={"service": "api", "status": "down", "checks_failed": "2"}
    )
    await asyncio.sleep(3)
    
    print("  → Resolving incident...")
    await am.resolve(
        type="infra",
        key=incident_key,
        resolution_message="API service recovered - all health checks passing"
    )
    await asyncio.sleep(2)
    
    print("✅ Incident lifecycle test completed")

async def test_severity_routing():
    """Test different severity levels with proper colors and emojis"""
    print("\n🧪 Test 4: Severity Routing & Formatting")
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    am = AlertManager(r, WEBHOOK_URL)
    
    severities = [
        ("info", "ℹ️ INFO", "Routine system update"),
        ("warning", "⚠️ WARNING", "Elevated latency detected"),
        ("critical", "🚨 CRITICAL", "System failure imminent")
    ]
    
    for severity, title, body in severities:
        print(f"  → Sending {severity.upper()} alert...")
        await am.send(
            type="test",
            severity=severity,
            key=f"severity-{severity}-{int(time.time())}",
            title=title,
            body=body,
            tags={"severity_test": "true"}
        )
        await asyncio.sleep(2)
    
    print("✅ Severity routing test completed - check Discord for color coding")

async def test_mute():
    """Test mute/unmute functionality"""
    print("\n🧪 Test 5: Mute/Unmute")
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    am = AlertManager(r, WEBHOOK_URL)
    
    print("  → Muting INFO level for 1 minute...")
    am.mute("info", duration_minutes=1)
    
    print("  → Trying to send INFO alert (should be suppressed)...")
    await am.send(
        type="test",
        severity="info",
        key=f"mute-test-{int(time.time())}",
        title="ℹ️ This should be muted",
        body="This INFO alert should not appear in Discord",
        tags={"muted": "should_be"}
    )
    await asyncio.sleep(2)
    
    print("  → Sending WARNING alert (should NOT be muted)...")
    await am.send(
        type="test",
        severity="warning",
        key=f"mute-warning-{int(time.time())}",
        title="⚠️ This should appear",
        body="WARNING alerts are not muted",
        tags={"muted": "no"}
    )
    await asyncio.sleep(2)
    
    print("  → Unmuting INFO level...")
    am.unmute("info")
    
    print("  → Sending INFO alert after unmute (should appear)...")
    await am.send(
        type="test",
        severity="info",
        key=f"unmute-test-{int(time.time())}",
        title="ℹ️ This should appear after unmute",
        body="INFO alerts are working again",
        tags={"muted": "no"}
    )
    await asyncio.sleep(2)
    
    print("✅ Mute/unmute test completed")

async def test_open_incidents():
    """Test getting open incidents"""
    print("\n🧪 Test 6: Open Incidents Tracking")
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    am = AlertManager(r, WEBHOOK_URL)
    
    print("  → Creating test incidents...")
    await am.send(
        type="test",
        severity="warning",
        key="incident-1",
        title="Test Incident 1",
        body="This is test incident 1"
    )
    await asyncio.sleep(1)
    
    await am.send(
        type="test",
        severity="critical",
        key="incident-2",
        title="Test Incident 2",
        body="This is test incident 2"
    )
    await asyncio.sleep(1)
    
    incidents = am.get_open_incidents()
    print(f"  → Found {len(incidents)} open incident(s)")
    for inc in incidents:
        print(f"    - {inc.get('title')} (severity: {inc.get('severity')})")
    
    print("✅ Open incidents test completed")

async def main():
    """Run all integration tests"""
    print("=" * 70)
    print("🚀 AlertManager Integration Test Suite")
    print("=" * 70)
    
    try:
        r = redis.Redis(host='localhost', port=6379, decode_responses=True)
        r.ping()
        print("✅ Redis connection OK")
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("Please start Redis: docker run -d -p 6379:6379 redis")
        return
    
    try:
        await test_basic_alert()
        await test_deduplication()
        await test_incident_lifecycle()
        await test_severity_routing()
        await test_mute()
        await test_open_incidents()
        
        print("\n" + "=" * 70)
        print("✅ All integration tests completed successfully!")
        print("=" * 70)
        print("\n📌 Check your Discord channel to verify:")
        print("  1. Alerts appeared with proper formatting")
        print("  2. Duplicate alerts updated the same message")
        print("  3. Incident lifecycle showed open -> update -> resolve")
        print("  4. Colors matched severity (gray/orange/red)")
        print("  5. Muted alerts were suppressed")
        print("  6. Open incidents were tracked correctly")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
