#!/usr/bin/env python3
import sys
import os
sys.path.append('/app')

os.chdir('/app')

try:
    from main import bot_state
    print('=== BOT_STATE VALUES ===')
    for key, value in bot_state.items():
        print(f'  {key}: {value}')
    
    print('\n=== CHECKING RISK SETTINGS FUNCTION ===')
    from main import app
    
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    smoke_trade_exists = "/api/test/smoke_trade" in routes
    print(f'Smoke trade route registered: {smoke_trade_exists}')
    
    if not smoke_trade_exists:
        print('Missing routes that should exist:')
        expected_routes = ['/api/test/smoke_trade', '/api/risk', '/api/debug/whoami']
        for route in expected_routes:
            if route not in routes:
                print(f'  MISSING: {route}')
    
    print(f'\nTotal registered routes: {len(routes)}')
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
