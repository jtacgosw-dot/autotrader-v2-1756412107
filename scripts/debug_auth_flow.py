#!/usr/bin/env python3
import sys
import os
sys.path.append('/app')

os.chdir('/app')

try:
    from main import users, load_credentials
    
    print('=== DEBUGGING AUTHENTICATION FLOW ===')
    print(f'Users dict keys: {list(users.keys())}')
    
    for username, user_data in users.items():
        print(f'\nUser: {username}')
        print(f'  Role: {user_data["role"]}')
        print(f'  Password (first 8 chars): {user_data["password"][:8]}...')
        print(f'  Password length: {len(user_data["password"])}')
    
    test_passwords = {
        'viewer': 'j10%m%!mjkdAPn4W',
        'controller': 'CP*FwzpdRmhvN9@X'
    }
    
    print('\n=== TESTING PASSWORD MATCHES ===')
    for username, test_password in test_passwords.items():
        if username in users:
            stored_password = users[username]["password"]
            match = stored_password == test_password
            print(f'{username}: stored="{stored_password}" test="{test_password}" match={match}')
        else:
            print(f'{username}: NOT FOUND in users dict')
    
    print('\n=== RELOADING CREDENTIALS ===')
    fresh_users = load_credentials()
    print(f'Fresh users keys: {list(fresh_users.keys())}')
    
    for username, user_data in fresh_users.items():
        print(f'\nFresh User: {username}')
        print(f'  Role: {user_data["role"]}')
        print(f'  Password (first 8 chars): {user_data["password"][:8]}...')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
