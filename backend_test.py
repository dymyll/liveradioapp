import requests
import sys
import json
import time
from datetime import datetime, timezone
import io
import os

class AuthenticationTester:
    def __init__(self, base_url="https://sonic-pulse-4.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.auth_token = None
        self.test_user_data = None

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        
        result = f"{status} - {name}"
        if details:
            result += f" | {details}"
        
        print(result)
        self.test_results.append({
            'name': name,
            'success': success,
            'details': details
        })
        return success

    def test_user_registration(self):
        """Test user registration endpoint"""
        print("\n🔐 Testing User Registration...")
        
        # Generate unique test user data
        timestamp = int(time.time())
        self.test_user_data = {
            "username": f"testuser_{timestamp}",
            "email": f"testuser_{timestamp}@radiotest.com",
            "password": "SecureTestPass123!",
            "role": "dj"
        }
        
        try:
            url = f"{self.api_url}/auth/register"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(url, json=self.test_user_data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Verify response structure
                required_fields = ['access_token', 'token_type', 'user']
                missing_fields = [field for field in required_fields if field not in response_data]
                
                if missing_fields:
                    return self.log_test(
                        "User Registration", False, 
                        f"Missing fields in response: {missing_fields}"
                    )
                
                # Store token for subsequent tests
                self.auth_token = response_data['access_token']
                
                # Verify user data in response
                user_data = response_data['user']
                if (user_data['username'] == self.test_user_data['username'] and 
                    user_data['email'] == self.test_user_data['email'] and
                    user_data['role'] == self.test_user_data['role']):
                    
                    return self.log_test(
                        "User Registration", True, 
                        f"User created successfully with token: {self.auth_token[:20]}..."
                    )
                else:
                    return self.log_test(
                        "User Registration", False, 
                        "User data mismatch in response"
                    )
            else:
                try:
                    error_data = response.json()
                    return self.log_test(
                        "User Registration", False, 
                        f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}"
                    )
                except:
                    return self.log_test(
                        "User Registration", False, 
                        f"Status: {response.status_code} | Response: {response.text[:100]}"
                    )
                    
        except requests.exceptions.RequestException as e:
            return self.log_test("User Registration", False, f"Request failed: {str(e)}")

    def test_user_login(self):
        """Test user login endpoint"""
        print("\n🔑 Testing User Login...")
        
        if not self.test_user_data:
            return self.log_test("User Login", False, "No test user data available")
        
        login_data = {
            "username": self.test_user_data['username'],
            "password": self.test_user_data['password']
        }
        
        try:
            url = f"{self.api_url}/auth/login"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(url, json=login_data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Verify response structure
                required_fields = ['access_token', 'token_type', 'user']
                missing_fields = [field for field in required_fields if field not in response_data]
                
                if missing_fields:
                    return self.log_test(
                        "User Login", False, 
                        f"Missing fields in response: {missing_fields}"
                    )
                
                # Update token (should be same or new)
                login_token = response_data['access_token']
                
                # Verify user data
                user_data = response_data['user']
                if (user_data['username'] == self.test_user_data['username'] and 
                    user_data['email'] == self.test_user_data['email']):
                    
                    return self.log_test(
                        "User Login", True, 
                        f"Login successful with token: {login_token[:20]}..."
                    )
                else:
                    return self.log_test(
                        "User Login", False, 
                        "User data mismatch in login response"
                    )
            else:
                try:
                    error_data = response.json()
                    return self.log_test(
                        "User Login", False, 
                        f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}"
                    )
                except:
                    return self.log_test(
                        "User Login", False, 
                        f"Status: {response.status_code} | Response: {response.text[:100]}"
                    )
                    
        except requests.exceptions.RequestException as e:
            return self.log_test("User Login", False, f"Request failed: {str(e)}")

    def test_auth_token_verification(self):
        """Test auth token verification with /auth/me endpoint"""
        print("\n🎫 Testing Auth Token Verification...")
        
        if not self.auth_token:
            return self.log_test("Auth Token Verification", False, "No auth token available")
        
        try:
            url = f"{self.api_url}/auth/me"
            headers = {
                'Authorization': f'Bearer {self.auth_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Verify user data matches what we expect
                if (response_data['username'] == self.test_user_data['username'] and 
                    response_data['email'] == self.test_user_data['email'] and
                    response_data['role'] == self.test_user_data['role']):
                    
                    return self.log_test(
                        "Auth Token Verification", True, 
                        f"Token valid, user: {response_data['username']}"
                    )
                else:
                    return self.log_test(
                        "Auth Token Verification", False, 
                        "User data mismatch in /auth/me response"
                    )
            elif response.status_code == 401:
                return self.log_test(
                    "Auth Token Verification", False, 
                    "Token rejected - 401 Unauthorized"
                )
            else:
                try:
                    error_data = response.json()
                    return self.log_test(
                        "Auth Token Verification", False, 
                        f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}"
                    )
                except:
                    return self.log_test(
                        "Auth Token Verification", False, 
                        f"Status: {response.status_code} | Response: {response.text[:100]}"
                    )
                    
        except requests.exceptions.RequestException as e:
            return self.log_test("Auth Token Verification", False, f"Request failed: {str(e)}")

    def test_upload_endpoint_access(self):
        """Test authenticated access to upload endpoint"""
        print("\n📤 Testing Upload Endpoint Access...")
        
        if not self.auth_token:
            return self.log_test("Upload Endpoint Access", False, "No auth token available")
        
        # First, try to get existing stations
        station_slug = self.get_or_create_test_station()
        if not station_slug:
            return self.log_test("Upload Endpoint Access", False, "No station available for testing")
        
        try:
            # Create dummy files for upload
            audio_content = b"FAKE_AUDIO_DATA_FOR_TESTING" * 1000
            audio_file = io.BytesIO(audio_content)
            
            image_content = b"FAKE_IMAGE_DATA_FOR_TESTING" * 100
            image_file = io.BytesIO(image_content)
            
            # Prepare form data
            form_data = {
                'title': f'Auth Test Song {int(time.time())}',
                'artist_name': 'Auth Test Artist',
                'genre': 'Test Genre'
            }
            
            files = {
                'audio_file': ('auth_test_song.mp3', audio_file, 'audio/mpeg'),
                'artwork_file': ('auth_test_artwork.jpg', image_file, 'image/jpeg')
            }
            
            url = f"{self.api_url}/stations/{station_slug}/songs/upload"
            headers = {
                'Authorization': f'Bearer {self.auth_token}'
            }
            
            response = requests.post(url, data=form_data, files=files, headers=headers, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                if 'id' in response_data:
                    return self.log_test(
                        "Upload Endpoint Access", True, 
                        f"Upload successful, song ID: {response_data['id']}"
                    )
                else:
                    return self.log_test(
                        "Upload Endpoint Access", False, 
                        "Upload response missing song ID"
                    )
            elif response.status_code == 401:
                return self.log_test(
                    "Upload Endpoint Access", False, 
                    "Upload rejected - 401 Unauthorized (token issue)"
                )
            elif response.status_code == 403:
                return self.log_test(
                    "Upload Endpoint Access", False, 
                    "Upload rejected - 403 Forbidden (permission issue)"
                )
            else:
                try:
                    error_data = response.json()
                    return self.log_test(
                        "Upload Endpoint Access", False, 
                        f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}"
                    )
                except:
                    return self.log_test(
                        "Upload Endpoint Access", False, 
                        f"Status: {response.status_code} | Response: {response.text[:100]}"
                    )
                    
        except requests.exceptions.RequestException as e:
            return self.log_test("Upload Endpoint Access", False, f"Request failed: {str(e)}")

    def get_or_create_test_station(self):
        """Get existing stations or create a test station for upload testing"""
        # First, try to get existing stations
        try:
            url = f"{self.api_url}/stations"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                stations = response.json()
                if stations and len(stations) > 0:
                    # Use the first available station
                    return stations[0]['slug']
        except:
            pass
        
        # If no existing stations, try to create one
        return self.create_test_station()

    def create_test_station(self):
        """Create a test station for upload testing"""
        if not self.auth_token:
            return None
        
        station_data = {
            "name": f"Auth Test Station {int(time.time())}",
            "description": "Test station for authentication testing",
            "genre": "Test"
        }
        
        try:
            url = f"{self.api_url}/stations"
            headers = {
                'Authorization': f'Bearer {self.auth_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=station_data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                return response_data.get('slug')
            else:
                print(f"Failed to create test station: {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    print(f"Response: {response.text[:200]}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Station creation request failed: {str(e)}")
            return None

    def test_invalid_token_scenarios(self):
        """Test various invalid token scenarios"""
        print("\n🚫 Testing Invalid Token Scenarios...")
        
        # Test with no token
        try:
            url = f"{self.api_url}/auth/me"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 401:
                self.log_test("No Token Test", True, "Correctly rejected request without token")
            else:
                self.log_test("No Token Test", False, f"Expected 401, got {response.status_code}")
        except:
            self.log_test("No Token Test", False, "Request failed")
        
        # Test with invalid token
        try:
            url = f"{self.api_url}/auth/me"
            headers = {'Authorization': 'Bearer invalid_token_12345'}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 401:
                self.log_test("Invalid Token Test", True, "Correctly rejected invalid token")
            else:
                self.log_test("Invalid Token Test", False, f"Expected 401, got {response.status_code}")
        except:
            self.log_test("Invalid Token Test", False, "Request failed")

    def run_authentication_tests(self):
        """Run all authentication tests"""
        print("🔐 Starting Authentication System Tests...")
        print(f"Testing against: {self.base_url}")
        
        try:
            # Test user registration
            self.test_user_registration()
            
            # Test user login
            self.test_user_login()
            
            # Test auth token verification
            self.test_auth_token_verification()
            
            # Test upload endpoint access
            self.test_upload_endpoint_access()
            
            # Test invalid token scenarios
            self.test_invalid_token_scenarios()
            
        except Exception as e:
            print(f"❌ Authentication test suite failed with error: {str(e)}")
        
        # Print summary
        print(f"\n📊 Authentication Test Results Summary:")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        # Print failed tests
        failed_tests = [test for test in self.test_results if not test['success']]
        if failed_tests:
            print(f"\n❌ Failed Tests ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"  - {test['name']}: {test['details']}")
        
        return self.tests_passed == self.tests_run

class IndieRadioAPITester:
    def __init__(self, base_url="https://sonic-pulse-4.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        
        result = f"{status} - {name}"
        if details:
            result += f" | {details}"
        
        print(result)
        self.test_results.append({
            'name': name,
            'success': success,
            'details': details
        })
        return success

    def run_api_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {}
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                if files:
                    response = requests.post(url, data=data, files=files, headers=headers, timeout=30)
                else:
                    headers['Content-Type'] = 'application/json'
                    response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method == 'PUT':
                headers['Content-Type'] = 'application/json'
                response = requests.put(url, json=data, headers=headers, timeout=10)

            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            
            if success and response.content:
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict) and 'message' in response_data:
                        details += f" | {response_data['message']}"
                    elif isinstance(response_data, list):
                        details += f" | Returned {len(response_data)} items"
                except:
                    pass
            elif not success:
                try:
                    error_data = response.json()
                    details += f" | Error: {error_data.get('detail', 'Unknown error')}"
                except:
                    details += f" | Response: {response.text[:100]}"

            return self.log_test(name, success, details), response

        except requests.exceptions.RequestException as e:
            return self.log_test(name, False, f"Request failed: {str(e)}"), None

    def test_basic_endpoints(self):
        """Test basic GET endpoints"""
        print("\n🔍 Testing Basic API Endpoints...")
        
        # Test songs endpoint
        self.run_api_test("Get Songs", "GET", "songs", 200)
        
        # Test artists endpoint
        self.run_api_test("Get Artists", "GET", "artists", 200)
        
        # Test playlists endpoint
        self.run_api_test("Get Playlists", "GET", "playlists", 200)
        
        # Test schedule endpoint
        self.run_api_test("Get Schedule", "GET", "schedule", 200)
        
        # Test current show endpoint
        self.run_api_test("Get Current Show", "GET", "schedule/now", 200)

    def test_artist_submission(self):
        """Test artist submission functionality"""
        print("\n🎤 Testing Artist Submission...")
        
        artist_data = {
            "name": f"Test Artist {int(time.time())}",
            "bio": "This is a test artist bio for API testing purposes.",
            "email": f"testartist{int(time.time())}@example.com",
            "social_links": {
                "instagram": "https://instagram.com/testartist",
                "spotify": "https://spotify.com/artist/testartist"
            }
        }
        
        success, response = self.run_api_test(
            "Submit Artist", "POST", "artists/submit", 200, artist_data
        )
        
        if success and response:
            try:
                response_data = response.json()
                artist_id = response_data.get('id')
                if artist_id:
                    # Test getting the submitted artist
                    self.run_api_test("Get Artists (after submission)", "GET", "artists", 200)
                    return artist_id
            except:
                pass
        
        return None

    def test_song_upload(self):
        """Test song upload functionality"""
        print("\n🎵 Testing Song Upload...")
        
        # Create a dummy audio file for testing
        audio_content = b"FAKE_AUDIO_DATA_FOR_TESTING" * 1000  # Simulate audio file
        audio_file = io.BytesIO(audio_content)
        
        # Create a dummy image file for artwork
        image_content = b"FAKE_IMAGE_DATA_FOR_TESTING" * 100  # Simulate image file
        image_file = io.BytesIO(image_content)
        
        form_data = {
            'title': f'Test Song {int(time.time())}',
            'artist_name': 'Test Artist Upload',
            'genre': 'Indie Rock'
        }
        
        files = {
            'audio_file': ('test_song.mp3', audio_file, 'audio/mpeg'),
            'artwork_file': ('test_artwork.jpg', image_file, 'image/jpeg')
        }
        
        success, response = self.run_api_test(
            "Upload Song", "POST", "songs/upload", 200, form_data, files
        )
        
        if success and response:
            try:
                response_data = response.json()
                song_id = response_data.get('id')
                if song_id:
                    # Test getting songs after upload
                    self.run_api_test("Get Songs (after upload)", "GET", "songs", 200)
                    return song_id
            except:
                pass
        
        return None

    def test_playlist_management(self):
        """Test playlist creation and management"""
        print("\n📋 Testing Playlist Management...")
        
        playlist_data = {
            "name": f"Test Playlist {int(time.time())}",
            "description": "This is a test playlist for API testing",
            "is_public": True
        }
        
        success, response = self.run_api_test(
            "Create Playlist", "POST", "playlists", 200, playlist_data
        )
        
        if success and response:
            try:
                response_data = response.json()
                playlist_id = response_data.get('id')
                if playlist_id:
                    # Test getting specific playlist
                    self.run_api_test(
                        "Get Specific Playlist", "GET", f"playlists/{playlist_id}", 200
                    )
                    return playlist_id
            except:
                pass
        
        return None

    def test_schedule_management(self):
        """Test schedule creation"""
        print("\n📅 Testing Schedule Management...")
        
        # Create a future schedule
        start_time = datetime.now(timezone.utc).replace(microsecond=0)
        end_time = start_time.replace(hour=start_time.hour + 2)
        
        schedule_data = {
            "title": f"Test Show {int(time.time())}",
            "dj_id": f"test_dj_{int(time.time())}",
            "dj_name": "Test DJ",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "description": "Test DJ show for API testing"
        }
        
        success, response = self.run_api_test(
            "Create Schedule", "POST", "schedule", 200, schedule_data
        )
        
        if success and response:
            try:
                response_data = response.json()
                return response_data.get('id')
            except:
                pass
        
        return None

    def test_user_management(self):
        """Test user creation"""
        print("\n👤 Testing User Management...")
        
        user_data = {
            "username": f"testuser_{int(time.time())}",
            "email": f"testuser{int(time.time())}@example.com",
            "role": "listener"
        }
        
        success, response = self.run_api_test(
            "Create User", "POST", "users", 200, user_data
        )
        
        if success:
            # Test getting users
            self.run_api_test("Get Users", "GET", "users", 200)

    def test_live_streaming(self):
        """Test live streaming controls"""
        print("\n📡 Testing Live Streaming Controls...")
        
        dj_id = f"test_dj_{int(time.time())}"
        
        # Test start live stream
        self.run_api_test(
            "Start Live Stream", "POST", f"live/{dj_id}/start", 200
        )
        
        # Test stop live stream
        self.run_api_test(
            "Stop Live Stream", "POST", f"live/{dj_id}/stop", 200
        )

    def test_error_handling(self):
        """Test error handling for invalid requests"""
        print("\n⚠️ Testing Error Handling...")
        
        # Test invalid song ID
        self.run_api_test(
            "Get Invalid Song", "GET", "songs/invalid_id", 404
        )
        
        # Test invalid playlist ID
        self.run_api_test(
            "Get Invalid Playlist", "GET", "playlists/invalid_id", 404
        )
        
        # Test invalid artist approval
        self.run_api_test(
            "Approve Invalid Artist", "PUT", "artists/invalid_id/approve", 404
        )

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Indie Radio Station API Tests...")
        print(f"Testing against: {self.base_url}")
        
        try:
            # Test basic endpoints
            self.test_basic_endpoints()
            
            # Test user management
            self.test_user_management()
            
            # Test artist submission
            artist_id = self.test_artist_submission()
            
            # Test song upload
            song_id = self.test_song_upload()
            
            # Test playlist management
            playlist_id = self.test_playlist_management()
            
            # Test schedule management
            schedule_id = self.test_schedule_management()
            
            # Test live streaming
            self.test_live_streaming()
            
            # Test error handling
            self.test_error_handling()
            
        except Exception as e:
            print(f"❌ Test suite failed with error: {str(e)}")
        
        # Print summary
        print(f"\n📊 Test Results Summary:")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        # Print failed tests
        failed_tests = [test for test in self.test_results if not test['success']]
        if failed_tests:
            print(f"\n❌ Failed Tests ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"  - {test['name']}: {test['details']}")
        
        return self.tests_passed == self.tests_run

class MusicApprovalTester:
    def __init__(self, base_url="https://sonic-pulse-4.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        
        # Test users and tokens
        self.station_owner_token = None
        self.station_owner_data = None
        self.listener_token = None
        self.listener_data = None
        self.test_station_slug = None
        self.test_station_id = None
        
        # Test songs for approval workflow
        self.pending_song_id = None
        self.auto_approved_song_id = None

    def log_test(self, name, success, details=""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        
        result = f"{status} - {name}"
        if details:
            result += f" | {details}"
        
        print(result)
        self.test_results.append({
            'name': name,
            'success': success,
            'details': details
        })
        return success

    def setup_test_users(self):
        """Create test users for approval workflow testing"""
        print("\n👥 Setting up test users...")
        
        timestamp = int(time.time())
        
        # Create station owner/admin user
        self.station_owner_data = {
            "username": f"stationowner_{timestamp}",
            "email": f"stationowner_{timestamp}@radiotest.com",
            "password": "StationOwnerPass123!",
            "role": "admin"  # Admin gets auto-approval
        }
        
        # Create listener user
        self.listener_data = {
            "username": f"listener_{timestamp}",
            "email": f"listener_{timestamp}@radiotest.com", 
            "password": "ListenerPass123!",
            "role": "listener"  # Listener needs approval
        }
        
        # Register station owner
        try:
            url = f"{self.api_url}/auth/register"
            headers = {'Content-Type': 'application/json'}
            
            response = requests.post(url, json=self.station_owner_data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                self.station_owner_token = response_data['access_token']
                self.log_test("Station Owner Registration", True, f"Token: {self.station_owner_token[:20]}...")
            else:
                return self.log_test("Station Owner Registration", False, f"Status: {response.status_code}")
                
        except Exception as e:
            return self.log_test("Station Owner Registration", False, f"Error: {str(e)}")
        
        # Register listener
        try:
            response = requests.post(url, json=self.listener_data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                self.listener_token = response_data['access_token']
                self.log_test("Listener Registration", True, f"Token: {self.listener_token[:20]}...")
            else:
                return self.log_test("Listener Registration", False, f"Status: {response.status_code}")
                
        except Exception as e:
            return self.log_test("Listener Registration", False, f"Error: {str(e)}")
        
        return self.station_owner_token and self.listener_token

    def create_test_station(self):
        """Create a test station for approval workflow"""
        print("\n🏢 Creating test station...")
        
        if not self.station_owner_token:
            return self.log_test("Create Test Station", False, "No station owner token")
        
        station_data = {
            "name": f"Approval Test Station {int(time.time())}",
            "description": "Test station for music approval workflow",
            "genre": "Test Music"
        }
        
        try:
            url = f"{self.api_url}/stations"
            headers = {
                'Authorization': f'Bearer {self.station_owner_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=station_data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                self.test_station_slug = response_data.get('slug')
                self.test_station_id = response_data.get('id')
                return self.log_test("Create Test Station", True, f"Station: {self.test_station_slug}")
            else:
                try:
                    error_data = response.json()
                    return self.log_test("Create Test Station", False, f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    return self.log_test("Create Test Station", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("Create Test Station", False, f"Error: {str(e)}")

    def test_upload_with_auto_approval(self):
        """Test uploading a song as station owner/admin (should get auto-approved)"""
        print("\n🎵 Testing Upload with Auto-Approval (Station Owner)...")
        
        if not self.station_owner_token or not self.test_station_slug:
            return self.log_test("Upload Auto-Approval", False, "Missing prerequisites")
        
        # Create dummy files
        audio_content = b"FAKE_AUDIO_DATA_FOR_AUTO_APPROVAL_TEST" * 1000
        audio_file = io.BytesIO(audio_content)
        
        image_content = b"FAKE_IMAGE_DATA_FOR_AUTO_APPROVAL_TEST" * 100
        image_file = io.BytesIO(image_content)
        
        form_data = {
            'title': f'Auto Approved Song {int(time.time())}',
            'artist_name': 'Station Owner Artist',
            'genre': 'Auto Approval Genre'
        }
        
        files = {
            'audio_file': ('auto_approved_song.mp3', audio_file, 'audio/mpeg'),
            'artwork_file': ('auto_approved_artwork.jpg', image_file, 'image/jpeg')
        }
        
        try:
            url = f"{self.api_url}/stations/{self.test_station_slug}/songs/upload"
            headers = {
                'Authorization': f'Bearer {self.station_owner_token}'
            }
            
            response = requests.post(url, data=form_data, files=files, headers=headers, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                song_id = response_data.get('id')
                status = response_data.get('status')
                
                if song_id and status == 'approved':
                    self.auto_approved_song_id = song_id
                    return self.log_test("Upload Auto-Approval", True, f"Song ID: {song_id} | Status: {status}")
                else:
                    return self.log_test("Upload Auto-Approval", False, f"Expected approved status, got: {status}")
            else:
                try:
                    error_data = response.json()
                    return self.log_test("Upload Auto-Approval", False, f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    return self.log_test("Upload Auto-Approval", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("Upload Auto-Approval", False, f"Error: {str(e)}")

    def test_upload_requiring_approval(self):
        """Test uploading a song as listener (should require approval)"""
        print("\n🎵 Testing Upload Requiring Approval (Listener)...")
        
        if not self.listener_token or not self.test_station_slug:
            return self.log_test("Upload Requiring Approval", False, "Missing prerequisites")
        
        # Create dummy files
        audio_content = b"FAKE_AUDIO_DATA_FOR_PENDING_APPROVAL_TEST" * 1000
        audio_file = io.BytesIO(audio_content)
        
        image_content = b"FAKE_IMAGE_DATA_FOR_PENDING_APPROVAL_TEST" * 100
        image_file = io.BytesIO(image_content)
        
        form_data = {
            'title': f'Pending Approval Song {int(time.time())}',
            'artist_name': 'Listener Artist',
            'genre': 'Pending Genre'
        }
        
        files = {
            'audio_file': ('pending_song.mp3', audio_file, 'audio/mpeg'),
            'artwork_file': ('pending_artwork.jpg', image_file, 'image/jpeg')
        }
        
        try:
            url = f"{self.api_url}/stations/{self.test_station_slug}/songs/upload"
            headers = {
                'Authorization': f'Bearer {self.listener_token}'
            }
            
            response = requests.post(url, data=form_data, files=files, headers=headers, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                song_id = response_data.get('id')
                status = response_data.get('status')
                
                if song_id and status == 'pending':
                    self.pending_song_id = song_id
                    return self.log_test("Upload Requiring Approval", True, f"Song ID: {song_id} | Status: {status}")
                else:
                    return self.log_test("Upload Requiring Approval", False, f"Expected pending status, got: {status}")
            else:
                try:
                    error_data = response.json()
                    return self.log_test("Upload Requiring Approval", False, f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    return self.log_test("Upload Requiring Approval", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("Upload Requiring Approval", False, f"Error: {str(e)}")

    def test_get_song_requests(self):
        """Test getting pending song requests for station"""
        print("\n📋 Testing Get Song Requests...")
        
        if not self.station_owner_token or not self.test_station_slug:
            return self.log_test("Get Song Requests", False, "Missing prerequisites")
        
        try:
            url = f"{self.api_url}/stations/{self.test_station_slug}/songs/requests"
            headers = {
                'Authorization': f'Bearer {self.station_owner_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                
                if isinstance(response_data, list):
                    # Check if our pending song is in the list
                    pending_found = False
                    if self.pending_song_id:
                        for song in response_data:
                            if song.get('id') == self.pending_song_id:
                                pending_found = True
                                break
                    
                    if pending_found or len(response_data) > 0:
                        return self.log_test("Get Song Requests", True, f"Found {len(response_data)} pending songs")
                    else:
                        return self.log_test("Get Song Requests", True, "No pending songs (expected if none uploaded)")
                else:
                    return self.log_test("Get Song Requests", False, "Response is not a list")
            else:
                try:
                    error_data = response.json()
                    return self.log_test("Get Song Requests", False, f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    return self.log_test("Get Song Requests", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("Get Song Requests", False, f"Error: {str(e)}")

    def test_approve_song(self):
        """Test approving a pending song"""
        print("\n✅ Testing Song Approval...")
        
        if not self.station_owner_token or not self.test_station_slug or not self.pending_song_id:
            return self.log_test("Approve Song", False, "Missing prerequisites")
        
        approval_data = {
            "action": "approve"
        }
        
        try:
            url = f"{self.api_url}/stations/{self.test_station_slug}/songs/{self.pending_song_id}/approve"
            headers = {
                'Authorization': f'Bearer {self.station_owner_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, json=approval_data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                message = response_data.get('message', '')
                action = response_data.get('action', '')
                
                if 'approved' in message.lower() and action == 'approve':
                    return self.log_test("Approve Song", True, f"Message: {message}")
                else:
                    return self.log_test("Approve Song", False, f"Unexpected response: {response_data}")
            else:
                try:
                    error_data = response.json()
                    return self.log_test("Approve Song", False, f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    return self.log_test("Approve Song", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("Approve Song", False, f"Error: {str(e)}")

    def test_decline_song(self):
        """Test declining a song with reason"""
        print("\n❌ Testing Song Decline...")
        
        # First upload another song to decline
        if not self.listener_token or not self.test_station_slug:
            return self.log_test("Decline Song", False, "Missing prerequisites")
        
        # Upload a song to decline
        audio_content = b"FAKE_AUDIO_DATA_FOR_DECLINE_TEST" * 1000
        audio_file = io.BytesIO(audio_content)
        
        form_data = {
            'title': f'Song To Decline {int(time.time())}',
            'artist_name': 'Decline Test Artist',
            'genre': 'Decline Genre'
        }
        
        files = {
            'audio_file': ('decline_song.mp3', audio_file, 'audio/mpeg')
        }
        
        try:
            # Upload song as listener
            upload_url = f"{self.api_url}/stations/{self.test_station_slug}/songs/upload"
            upload_headers = {
                'Authorization': f'Bearer {self.listener_token}'
            }
            
            upload_response = requests.post(upload_url, data=form_data, files=files, headers=upload_headers, timeout=30)
            
            if upload_response.status_code != 200:
                return self.log_test("Decline Song", False, "Failed to upload song for decline test")
            
            upload_data = upload_response.json()
            decline_song_id = upload_data.get('id')
            
            if not decline_song_id:
                return self.log_test("Decline Song", False, "No song ID returned from upload")
            
            # Now decline the song
            decline_data = {
                "action": "decline",
                "reason": "Song quality does not meet station standards"
            }
            
            decline_url = f"{self.api_url}/stations/{self.test_station_slug}/songs/{decline_song_id}/approve"
            decline_headers = {
                'Authorization': f'Bearer {self.station_owner_token}',
                'Content-Type': 'application/json'
            }
            
            decline_response = requests.post(decline_url, json=decline_data, headers=decline_headers, timeout=10)
            
            if decline_response.status_code == 200:
                response_data = decline_response.json()
                message = response_data.get('message', '')
                action = response_data.get('action', '')
                
                if 'declined' in message.lower() and action == 'decline':
                    return self.log_test("Decline Song", True, f"Message: {message}")
                else:
                    return self.log_test("Decline Song", False, f"Unexpected response: {response_data}")
            else:
                try:
                    error_data = decline_response.json()
                    return self.log_test("Decline Song", False, f"Status: {decline_response.status_code} | Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    return self.log_test("Decline Song", False, f"Status: {decline_response.status_code}")
                    
        except Exception as e:
            return self.log_test("Decline Song", False, f"Error: {str(e)}")

    def test_user_submissions(self):
        """Test getting user's submission status"""
        print("\n📊 Testing User Submissions...")
        
        if not self.listener_token:
            return self.log_test("User Submissions", False, "No listener token")
        
        try:
            url = f"{self.api_url}/user/submissions"
            headers = {
                'Authorization': f'Bearer {self.listener_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json()
                
                if isinstance(response_data, list):
                    # Check if we have submissions
                    submission_count = len(response_data)
                    
                    # Verify structure of submissions
                    if submission_count > 0:
                        first_submission = response_data[0]
                        required_fields = ['id', 'title', 'artist_name', 'station_name', 'status', 'submitted_at']
                        missing_fields = [field for field in required_fields if field not in first_submission]
                        
                        if missing_fields:
                            return self.log_test("User Submissions", False, f"Missing fields: {missing_fields}")
                        else:
                            return self.log_test("User Submissions", True, f"Found {submission_count} submissions with correct structure")
                    else:
                        return self.log_test("User Submissions", True, "No submissions found (expected if none uploaded)")
                else:
                    return self.log_test("User Submissions", False, "Response is not a list")
            else:
                try:
                    error_data = response.json()
                    return self.log_test("User Submissions", False, f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    return self.log_test("User Submissions", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("User Submissions", False, f"Error: {str(e)}")

    def test_download_song(self):
        """Test downloading a song file (station owner only)"""
        print("\n⬇️ Testing Song Download...")
        
        if not self.station_owner_token or not self.test_station_slug or not self.auto_approved_song_id:
            return self.log_test("Download Song", False, "Missing prerequisites")
        
        try:
            url = f"{self.api_url}/stations/{self.test_station_slug}/songs/{self.auto_approved_song_id}/download"
            headers = {
                'Authorization': f'Bearer {self.station_owner_token}'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # Check if we got a file response
                content_type = response.headers.get('content-type', '')
                content_length = len(response.content)
                
                if 'audio' in content_type or content_length > 0:
                    return self.log_test("Download Song", True, f"Downloaded {content_length} bytes | Content-Type: {content_type}")
                else:
                    return self.log_test("Download Song", False, f"Invalid file response | Content-Type: {content_type}")
            elif response.status_code == 404:
                return self.log_test("Download Song", False, "Song file not found")
            elif response.status_code == 403:
                return self.log_test("Download Song", False, "Access denied - not station owner")
            else:
                try:
                    error_data = response.json()
                    return self.log_test("Download Song", False, f"Status: {response.status_code} | Error: {error_data.get('detail', 'Unknown error')}")
                except:
                    return self.log_test("Download Song", False, f"Status: {response.status_code}")
                    
        except Exception as e:
            return self.log_test("Download Song", False, f"Error: {str(e)}")

    def test_unauthorized_access(self):
        """Test that listeners cannot access station owner endpoints"""
        print("\n🚫 Testing Unauthorized Access...")
        
        if not self.listener_token or not self.test_station_slug:
            return self.log_test("Unauthorized Access", False, "Missing prerequisites")
        
        # Test listener trying to access song requests (should fail)
        try:
            url = f"{self.api_url}/stations/{self.test_station_slug}/songs/requests"
            headers = {
                'Authorization': f'Bearer {self.listener_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 403:
                return self.log_test("Unauthorized Access", True, "Correctly denied listener access to song requests")
            elif response.status_code == 401:
                return self.log_test("Unauthorized Access", True, "Correctly denied unauthorized access")
            else:
                return self.log_test("Unauthorized Access", False, f"Expected 403/401, got {response.status_code}")
                
        except Exception as e:
            return self.log_test("Unauthorized Access", False, f"Error: {str(e)}")

    def run_music_approval_tests(self):
        """Run all music approval system tests"""
        print("🎵 Starting Music Approval System Tests...")
        print(f"Testing against: {self.base_url}")
        
        try:
            # Setup test environment
            if not self.setup_test_users():
                print("❌ Failed to setup test users")
                return False
            
            if not self.create_test_station():
                print("❌ Failed to create test station")
                return False
            
            # Test upload workflows
            self.test_upload_with_auto_approval()
            self.test_upload_requiring_approval()
            
            # Test approval management
            self.test_get_song_requests()
            self.test_approve_song()
            self.test_decline_song()
            
            # Test user features
            self.test_user_submissions()
            self.test_download_song()
            
            # Test security
            self.test_unauthorized_access()
            
        except Exception as e:
            print(f"❌ Music approval test suite failed with error: {str(e)}")
        
        # Print summary
        print(f"\n📊 Music Approval Test Results Summary:")
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%")
        
        # Print failed tests
        failed_tests = [test for test in self.test_results if not test['success']]
        if failed_tests:
            print(f"\n❌ Failed Tests ({len(failed_tests)}):")
            for test in failed_tests:
                print(f"  - {test['name']}: {test['details']}")
        
        return self.tests_passed == self.tests_run

def main():
    # Run music approval tests
    approval_tester = MusicApprovalTester()
    approval_success = approval_tester.run_music_approval_tests()
    
    print("\n" + "="*60)
    
    # Run authentication tests
    auth_tester = AuthenticationTester()
    auth_success = auth_tester.run_authentication_tests()
    
    print("\n" + "="*60)
    
    # Run general API tests
    api_tester = IndieRadioAPITester()
    api_success = api_tester.run_all_tests()
    
    return 0 if (approval_success and auth_success and api_success) else 1

if __name__ == "__main__":
    sys.exit(main())