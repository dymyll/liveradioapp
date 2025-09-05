#!/usr/bin/env python3

import requests
import json
import time

def debug_authentication():
    """Debug authentication issues step by step"""
    
    base_url = "https://sonic-pulse-4.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("🔍 Debugging Authentication Issues")
    print("=" * 50)
    
    # Create test user
    timestamp = int(time.time())
    user_data = {
        "username": f"debuguser_{timestamp}",
        "email": f"debuguser_{timestamp}@test.com",
        "password": "TestPass123!",
        "role": "artist"
    }
    
    # Register
    print("1. Registering user...")
    response = requests.post(f"{api_url}/auth/register", json=user_data)
    if response.status_code != 200:
        print(f"❌ Registration failed: {response.status_code} - {response.text}")
        return
    
    reg_data = response.json()
    token = reg_data['access_token']
    print(f"✅ User registered: {reg_data['user']['username']}")
    
    # Test /auth/me
    print("\n2. Testing /auth/me...")
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(f"{api_url}/auth/me", headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        user_info = response.json()
        print(f"   ✅ User info: {user_info['username']} ({user_info['role']})")
    else:
        print(f"   ❌ Failed: {response.text}")
        return
    
    # Test getting stations (public endpoint)
    print("\n3. Testing stations endpoint...")
    response = requests.get(f"{api_url}/stations")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        stations = response.json()
        print(f"   ✅ Found {len(stations)} stations")
        if stations:
            test_station = stations[0]
            print(f"   Using station: {test_station['name']} (slug: {test_station['slug']})")
        else:
            print("   ❌ No stations available")
            return
    else:
        print(f"   ❌ Failed: {response.text}")
        return
    
    # Test getting songs for the station (public endpoint)
    print(f"\n4. Testing songs for station {test_station['slug']}...")
    response = requests.get(f"{api_url}/stations/{test_station['slug']}/songs")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        songs = response.json()
        print(f"   ✅ Found {len(songs)} songs in station")
    else:
        print(f"   ❌ Failed: {response.text}")
    
    # Test upload with minimal data
    print(f"\n5. Testing upload with minimal data...")
    
    # Create minimal test file
    test_content = b"test audio content"
    
    form_data = {
        'title': 'Debug Test Song',
        'artist_name': 'Debug Artist'
    }
    
    files = {
        'audio_file': ('debug.mp3', test_content, 'audio/mpeg')
    }
    
    response = requests.post(
        f"{api_url}/stations/{test_station['slug']}/songs/upload",
        data=form_data,
        files=files,
        headers=headers
    )
    
    print(f"   Upload status: {response.status_code}")
    print(f"   Response headers: {dict(response.headers)}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ Upload successful: {result}")
    else:
        print(f"   ❌ Upload failed")
        print(f"   Response text: {response.text}")
        
        # Try to get more details
        try:
            error_data = response.json()
            print(f"   Error details: {error_data}")
        except:
            print(f"   Raw response: {response.text[:500]}")

if __name__ == "__main__":
    debug_authentication()