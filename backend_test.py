import requests
import sys
import json
import time
from datetime import datetime, timezone
import io
import os

class IndieRadioAPITester:
    def __init__(self, base_url="https://indie-music-station.preview.emergentagent.com"):
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
    tester = IndieRadioAPITester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())