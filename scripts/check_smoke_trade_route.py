#!/usr/bin/env python3
import sys
import os
sys.path.append('/home/ubuntu/autotrader/api')

try:
    from main import app
    print("=== FastAPI Routes Registration Check ===")
    
    routes = []
    for route in app.routes:
        if hasattr(route, 'path'):
            routes.append(f"{route.methods} {route.path}")
        elif hasattr(route, 'path_regex'):
            routes.append(f"REGEX {route.path_regex.pattern}")
    
    print("All registered routes:")
    for route in sorted(routes):
        print(f"  {route}")
    
    print("\nSmoke trade related routes:")
    smoke_routes = [r for r in routes if 'smoke' in r.lower()]
    if smoke_routes:
        for route in smoke_routes:
            print(f"  ✅ {route}")
    else:
        print("  ❌ No smoke trade routes found")
    
    print("\nTest endpoints:")
    test_routes = [r for r in routes if '/test/' in r]
    for route in test_routes:
        print(f"  {route}")
        
except Exception as e:
    print(f"Error checking routes: {e}")
    import traceback
    traceback.print_exc()
