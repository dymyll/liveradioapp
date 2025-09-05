#!/usr/bin/env python3

import requests
import json
import time
import io

def test_authentication_flow():
    """Test the complete authentication flow that the user is experiencing"""
    
    base_url = "https://sonic-pulse-4.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("🔐 Testing Authentication Flow for Upload Issue")
    print("=" * 60)
    
    # Step 1: Register a new user
    print("\n1️⃣ Testing User Registration...")
    timestamp = int(time.time())
    user_data = {
        "username": f"uploadtest_{timestamp}",
        "email": f"uploadtest_{timestamp}@radiotest.com", 
        "password": "TestPass123!",
        "role": "artist"  # Test with artist role as user mentioned
    }
    
    try:
        response = requests.post(f"{api_url}/auth/register", json=user_data, timeout=10)
        if response.status_code == 200:
            reg_data = response.json()
            token = reg_data['access_token']
            print(f"✅ Registration successful")
            print(f"   User: {reg_data['user']['username']}")
            print(f"   Role: {reg_data['user']['role']}")
            print(f"   Token: {token[:30]}...")
        else:
            print(f"❌ Registration failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Registration request failed: {e}")
        return False
    
    # Step 2: Test login
    print("\n2️⃣ Testing User Login...")
    login_data = {
        "username": user_data['username'],
        "password": user_data['password']
    }
    
    try:
        response = requests.post(f"{api_url}/auth/login", json=login_data, timeout=10)
        if response.status_code == 200:
            login_data = response.json()
            login_token = login_data['access_token']
            print(f"✅ Login successful")
            print(f"   Token: {login_token[:30]}...")
            # Use login token for subsequent tests
            token = login_token
        else:
            print(f"❌ Login failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Login request failed: {e}")
        return False
    
    # Step 3: Verify token with /auth/me
    print("\n3️⃣ Testing Token Verification...")
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(f"{api_url}/auth/me", headers=headers, timeout=10)
        if response.status_code == 200:
            user_info = response.json()
            print(f"✅ Token verification successful")
            print(f"   User: {user_info['username']}")
            print(f"   Role: {user_info['role']}")
            print(f"   Active: {user_info['is_active']}")
        else:
            print(f"❌ Token verification failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Token verification request failed: {e}")
        return False
    
    # Step 4: Test upload access (this is where the issue likely is)
    print("\n4️⃣ Testing Upload Endpoint Access...")
    
    # Get existing stations
    try:
        response = requests.get(f"{api_url}/stations", timeout=10)
        if response.status_code == 200:
            stations = response.json()
            if stations:
                test_station = stations[0]  # Use first available station
                station_slug = test_station['slug']
                print(f"   Using station: {test_station['name']} (slug: {station_slug})")
            else:
                print("❌ No stations available for testing")
                return False
        else:
            print(f"❌ Failed to get stations: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Failed to get stations: {e}")
        return False
    
    # Test upload endpoint
    print(f"\n   Testing upload to station: {station_slug}")
    
    # Create test files
    audio_content = b"FAKE_AUDIO_DATA" * 1000
    audio_file = io.BytesIO(audio_content)
    
    form_data = {
        'title': f'Test Upload {timestamp}',
        'artist_name': 'Test Artist',
        'genre': 'Test'
    }
    
    files = {
        'audio_file': ('test.mp3', audio_file, 'audio/mpeg')
    }
    
    try:
        upload_headers = {'Authorization': f'Bearer {token}'}
        response = requests.post(
            f"{api_url}/stations/{station_slug}/songs/upload",
            data=form_data,
            files=files,
            headers=upload_headers,
            timeout=30
        )
        
        print(f"   Upload response status: {response.status_code}")
        
        if response.status_code == 200:
            upload_result = response.json()
            print(f"✅ Upload successful!")
            print(f"   Song ID: {upload_result.get('id', 'N/A')}")
            print(f"   Message: {upload_result.get('message', 'N/A')}")
            return True
        elif response.status_code == 401:
            print(f"❌ Upload failed: 401 Unauthorized")
            print(f"   This suggests the token is not being accepted")
            print(f"   Error: {response.text}")
        elif response.status_code == 403:
            print(f"❌ Upload failed: 403 Forbidden")
            print(f"   This suggests the user doesn't have permission")
            print(f"   Error: {response.text}")
        else:
            print(f"❌ Upload failed: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"   Response: {response.text[:200]}")
        
        return False
        
    except Exception as e:
        print(f"❌ Upload request failed: {e}")
        return False

if __name__ == "__main__":
    success = test_authentication_flow()
    if success:
        print("\n🎉 All authentication tests passed!")
    else:
        print("\n💥 Authentication flow has issues!")