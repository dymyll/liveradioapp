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
            "role": "artist"
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
        
        # First, create a test station to upload to
        station_created = self.create_test_station()
        if not station_created:
            return self.log_test("Upload Endpoint Access", False, "Failed to create test station")
        
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
            
            url = f"{self.api_url}/stations/{self.test_station_slug}/songs/upload"
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

    def create_test_station(self):
        """Create a test station for upload testing"""
        if not self.auth_token:
            return False
        
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
                self.test_station_slug = response_data.get('slug')
                return bool(self.test_station_slug)
            else:
                print(f"Failed to create test station: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"Station creation request failed: {str(e)}")
            return False

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

def main():
    # Run authentication tests
    auth_tester = AuthenticationTester()
    auth_success = auth_tester.run_authentication_tests()
    
    print("\n" + "="*60)
    
    # Run general API tests
    api_tester = IndieRadioAPITester()
    api_success = api_tester.run_all_tests()
    
    return 0 if (auth_success and api_success) else 1

if __name__ == "__main__":
    sys.exit(main())