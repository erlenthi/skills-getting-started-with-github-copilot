"""
Tests for the Mergington High School Activities API
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src directory to path to import app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities

# Create test client
client = TestClient(app)

# Store original activities for reset between tests
ORIGINAL_ACTIVITIES = None


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities to original state before each test"""
    global ORIGINAL_ACTIVITIES
    # Store original on first run
    if ORIGINAL_ACTIVITIES is None:
        ORIGINAL_ACTIVITIES = {
            key: {**value, "participants": value["participants"].copy()}
            for key, value in activities.items()
        }
    
    # Reset before each test
    for key in activities:
        activities[key]["participants"] = ORIGINAL_ACTIVITIES[key]["participants"].copy()
    
    yield
    
    # Reset after each test
    for key in activities:
        activities[key]["participants"] = ORIGINAL_ACTIVITIES[key]["participants"].copy()


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self):
        """Test that GET /activities returns all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) == 9
        assert "Chess Club" in data
        assert "Programming Class" in data
    
    def test_activity_structure(self):
        """Test that each activity has the correct structure"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_data in data.items():
            assert "description" in activity_data
            assert "schedule" in activity_data
            assert "max_participants" in activity_data
            assert "participants" in activity_data
            assert isinstance(activity_data["participants"], list)
    
    def test_chess_club_has_initial_participants(self):
        """Test that Chess Club has the expected initial participants"""
        response = client.get("/activities")
        data = response.json()
        chess_club = data["Chess Club"]
        
        assert len(chess_club["participants"]) == 2
        assert "michael@mergington.edu" in chess_club["participants"]
        assert "daniel@mergington.edu" in chess_club["participants"]


class TestSignup:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_new_student(self):
        """Test signing up a new student for an activity"""
        response = client.post(
            "/activities/Chess Club/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        
        # Verify student was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Chess Club"]["participants"]
    
    def test_signup_duplicate_student(self):
        """Test that a student cannot sign up twice for the same activity"""
        # First signup
        response1 = client.post(
            "/activities/Chess Club/signup?email=michael@mergington.edu"
        )
        assert response1.status_code == 400
        assert "already signed up" in response1.json()["detail"]
    
    def test_signup_nonexistent_activity(self):
        """Test signing up for a non-existent activity"""
        response = client.post(
            "/activities/Nonexistent Activity/signup?email=student@mergington.edu"
        )
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_signup_multiple_activities(self):
        """Test that a student can sign up for multiple activities"""
        email = "versatile@mergington.edu"
        
        # Sign up for first activity
        response1 = client.post(
            f"/activities/Chess Club/signup?email={email}"
        )
        assert response1.status_code == 200
        
        # Sign up for second activity
        response2 = client.post(
            f"/activities/Programming Class/signup?email={email}"
        )
        assert response2.status_code == 200
        
        # Verify student is in both activities
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email in activities_data["Chess Club"]["participants"]
        assert email in activities_data["Programming Class"]["participants"]
    
    def test_signup_updates_availability(self):
        """Test that signup updates the availability count"""
        email = "newmember@mergington.edu"
        
        # Get initial availability
        initial_response = client.get("/activities")
        initial_data = initial_response.json()
        initial_available = (
            initial_data["Tennis Club"]["max_participants"] - 
            len(initial_data["Tennis Club"]["participants"])
        )
        
        # Sign up
        client.post(f"/activities/Tennis Club/signup?email={email}")
        
        # Get updated availability
        updated_response = client.get("/activities")
        updated_data = updated_response.json()
        updated_available = (
            updated_data["Tennis Club"]["max_participants"] - 
            len(updated_data["Tennis Club"]["participants"])
        )
        
        assert updated_available == initial_available - 1


class TestUnregister:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_existing_participant(self):
        """Test unregistering an existing participant"""
        response = client.delete(
            "/activities/Chess Club/unregister?email=michael@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "michael@mergington.edu" in data["message"]
        
        # Verify student was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "michael@mergington.edu" not in activities_data["Chess Club"]["participants"]
    
    def test_unregister_nonexistent_participant(self):
        """Test unregistering a student not in the activity"""
        response = client.delete(
            "/activities/Chess Club/unregister?email=notregistered@mergington.edu"
        )
        assert response.status_code == 400
        assert "not registered" in response.json()["detail"]
    
    def test_unregister_from_nonexistent_activity(self):
        """Test unregistering from a non-existent activity"""
        response = client.delete(
            "/activities/Nonexistent Activity/unregister?email=student@mergington.edu"
        )
        assert response.status_code == 404
        assert "Activity not found" in response.json()["detail"]
    
    def test_unregister_multiple_times(self):
        """Test that unregistering twice fails"""
        email = "temporary@mergington.edu"
        
        # Sign up first
        client.post(f"/activities/Basketball Team/signup?email={email}")
        
        # First unregister should succeed
        response1 = client.delete(
            f"/activities/Basketball Team/unregister?email={email}"
        )
        assert response1.status_code == 200
        
        # Second unregister should fail
        response2 = client.delete(
            f"/activities/Basketball Team/unregister?email={email}"
        )
        assert response2.status_code == 400
    
    def test_unregister_decreases_participant_count(self):
        """Test that unregistering decreases the participant count"""
        email = "testuser@mergington.edu"
        activity = "Programming Class"
        
        # Get initial count
        initial_response = client.get("/activities")
        initial_count = len(initial_response.json()[activity]["participants"])
        
        # Sign up
        client.post(f"/activities/{activity}/signup?email={email}")
        
        # Check count increased
        mid_response = client.get("/activities")
        mid_count = len(mid_response.json()[activity]["participants"])
        assert mid_count == initial_count + 1
        
        # Unregister
        client.delete(f"/activities/{activity}/unregister?email={email}")
        
        # Check count back to initial
        final_response = client.get("/activities")
        final_count = len(final_response.json()[activity]["participants"])
        assert final_count == initial_count


class TestRoot:
    """Tests for GET / endpoint"""
    
    def test_root_redirect(self):
        """Test that root endpoint redirects to static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"
    
    def test_root_follow_redirect(self):
        """Test following the redirect from root"""
        response = client.get("/", follow_redirects=True)
        assert response.status_code == 200


class TestIntegration:
    """Integration tests combining multiple operations"""
    
    def test_signup_and_unregister_workflow(self):
        """Test complete signup and unregister workflow"""
        email = "integrationtest@mergington.edu"
        activity = "Debate Team"
        
        # Get initial state
        initial = client.get("/activities").json()[activity]
        initial_count = len(initial["participants"])
        
        # Sign up
        response1 = client.post(f"/activities/{activity}/signup?email={email}")
        assert response1.status_code == 200
        
        # Verify signup
        after_signup = client.get("/activities").json()[activity]
        assert len(after_signup["participants"]) == initial_count + 1
        assert email in after_signup["participants"]
        
        # Unregister
        response2 = client.delete(f"/activities/{activity}/unregister?email={email}")
        assert response2.status_code == 200
        
        # Verify unregister
        after_unregister = client.get("/activities").json()[activity]
        assert len(after_unregister["participants"]) == initial_count
        assert email not in after_unregister["participants"]
    
    def test_multiple_signups_and_unregisters(self):
        """Test multiple signup and unregister operations"""
        activity = "Science Club"
        emails = ["user1@mergington.edu", "user2@mergington.edu", "user3@mergington.edu"]
        
        # Sign up all users
        for email in emails:
            response = client.post(f"/activities/{activity}/signup?email={email}")
            assert response.status_code == 200
        
        # Verify all signed up
        after_signups = client.get("/activities").json()[activity]
        for email in emails:
            assert email in after_signups["participants"]
        
        # Unregister all users
        for email in emails:
            response = client.delete(f"/activities/{activity}/unregister?email={email}")
            assert response.status_code == 200
        
        # Verify all unregistered
        after_unregisters = client.get("/activities").json()[activity]
        for email in emails:
            assert email not in after_unregisters["participants"]
