#!/usr/bin/env python3
import sys
import os
sys.path.append('/app')

os.chdir('/app')

try:
    from main import app
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    print('Registered FastAPI routes:')
    for route in sorted(routes):
        print(f'  {route}')
    print(f'\nTotal routes: {len(routes)}')
    print(f'Smoke trade route exists: {"/api/test/smoke_trade" in routes}')
    
    critical_endpoints = [
        '/api/test/smoke_trade',
        '/api/risk',
        '/api/debug/whoami',
        '/api/debug/cors'
    ]
    
    print('\nCritical endpoints check:')
    for endpoint in critical_endpoints:
        exists = endpoint in routes
        print(f'  {endpoint}: {"✓" if exists else "✗"}')
        
except Exception as e:
    print(f'Error importing main app: {e}')
    import traceback
    traceback.print_exc()
