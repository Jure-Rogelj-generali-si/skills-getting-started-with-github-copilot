"""
Tests for the FastAPI activities application
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app import app, activities


@pytest.fixture
def client():
    """Create a test client for the app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    # Save original state
    original = {k: {"participants": v["participants"].copy()} for k, v in activities.items()}
    yield
    # Restore after test
    for activity_name, data in original.items():
        activities[activity_name]["participants"] = data["participants"]


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_success(self, client, reset_activities):
        """Test retrieving all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        
        # Check structure of an activity
        activity = list(data.values())[0]
        assert "description" in activity
        assert "schedule" in activity
        assert "max_participants" in activity
        assert "participants" in activity
    
    def test_get_activities_contains_known_activity(self, client, reset_activities):
        """Test that known activities are in the response"""
        response = client.get("/activities")
        data = response.json()
        assert "Chess Club" in data
        assert "Programming Class" in data


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_success(self, client, reset_activities):
        """Test successful signup for an activity"""
        response = client.post(
            "/activities/Chess Club/signup?email=test@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "test@mergington.edu" in activities["Chess Club"]["participants"]
    
    def test_signup_activity_not_found(self, client, reset_activities):
        """Test signup for non-existent activity"""
        response = client.post(
            "/activities/Nonexistent Club/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "Activity not found" in data["detail"]
    
    def test_signup_already_registered(self, client, reset_activities):
        """Test signup for activity when already registered"""
        # First signup
        client.post("/activities/Chess Club/signup?email=duplicate@mergington.edu")
        # Try to signup again
        response = client.post(
            "/activities/Chess Club/signup?email=duplicate@mergington.edu"
        )
        assert response.status_code == 400
        data = response.json()
        assert "already signed up" in data["detail"]
    
    def test_signup_activity_full(self, client, reset_activities):
        """Test signup when activity is at max capacity"""
        activity = activities["Chess Club"]
        original_max = activity["max_participants"]
        
        # Fill up the activity
        activity["max_participants"] = len(activity["participants"])
        
        response = client.post(
            "/activities/Chess Club/signup?email=full@mergington.edu"
        )
        assert response.status_code == 400
        data = response.json()
        assert "no spots left" in data["detail"].lower()
        
        # Restore original max
        activity["max_participants"] = original_max
    
    def test_signup_valid_email(self, client, reset_activities):
        """Test that email parameter is required"""
        response = client.post("/activities/Chess Club/signup")
        # Should fail without email parameter
        assert response.status_code in [400, 422]


class TestUnregisterFromActivity:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_success(self, client, reset_activities):
        """Test successful unregistration from an activity"""
        email = "michael@mergington.edu"
        # Verify participant is registered
        assert email in activities["Chess Club"]["participants"]
        
        response = client.delete(
            f"/activities/Chess Club/unregister?email={email}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "Unregistered" in data["message"]
        # Verify participant is removed
        assert email not in activities["Chess Club"]["participants"]
    
    def test_unregister_activity_not_found(self, client, reset_activities):
        """Test unregister from non-existent activity"""
        response = client.delete(
            "/activities/Nonexistent Club/unregister?email=test@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "Activity not found" in data["detail"]
    
    def test_unregister_not_registered(self, client, reset_activities):
        """Test unregister when not registered"""
        response = client.delete(
            "/activities/Chess Club/unregister?email=notregistered@mergington.edu"
        )
        assert response.status_code == 400
        data = response.json()
        assert "not signed up" in data["detail"]
    
    def test_unregister_multiple_times(self, client, reset_activities):
        """Test unregister multiple times fails on second attempt"""
        email = "michael@mergington.edu"
        
        # First unregister should succeed
        response1 = client.delete(
            f"/activities/Chess Club/unregister?email={email}"
        )
        assert response1.status_code == 200
        
        # Second unregister should fail
        response2 = client.delete(
            f"/activities/Chess Club/unregister?email={email}"
        )
        assert response2.status_code == 400


class TestActivityCapacity:
    """Tests for activity capacity management"""
    
    def test_available_spots_calculation(self, client, reset_activities):
        """Test that available spots are calculated correctly"""
        response = client.get("/activities")
        data = response.json()
        
        chess_club = data["Chess Club"]
        expected_spots = (
            chess_club["max_participants"] - len(chess_club["participants"])
        )
        # This would be calculated on frontend, but verify data integrity
        assert chess_club["max_participants"] >= len(chess_club["participants"])
    
    def test_participants_list_integrity(self, client, reset_activities):
        """Test that participants list is properly maintained"""
        # Add a participant
        email = "new_student@mergington.edu"
        client.post(f"/activities/Chess Club/signup?email={email}")
        
        # Retrieve and verify
        response = client.get("/activities")
        data = response.json()
        assert email in data["Chess Club"]["participants"]


class TestRootRedirect:
    """Tests for root endpoint"""
    
    def test_root_redirect(self, client):
        """Test that root redirects to static files"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert "/static/index.html" in response.headers["location"]


class TestActivityParticipantOperations:
    """Integration tests for participant operations"""
    
    def test_signup_and_unregister_workflow(self, client, reset_activities):
        """Test complete signup and unregister workflow"""
        email = "workflow_test@mergington.edu"
        activity = "Programming Class"
        
        # Sign up
        signup_response = client.post(
            f"/activities/{activity}/signup?email={email}"
        )
        assert signup_response.status_code == 200
        assert email in activities[activity]["participants"]
        
        # Unregister
        unregister_response = client.delete(
            f"/activities/{activity}/unregister?email={email}"
        )
        assert unregister_response.status_code == 200
        assert email not in activities[activity]["participants"]
    
    def test_multiple_participants_in_activity(self, client, reset_activities):
        """Test managing multiple participants in same activity"""
        activity = "Basketball Team"
        emails = [
            "player1@mergington.edu",
            "player2@mergington.edu",
            "player3@mergington.edu"
        ]
        
        # Sign up multiple participants
        for email in emails:
            response = client.post(
                f"/activities/{activity}/signup?email={email}"
            )
            assert response.status_code == 200
        
        # Verify all are in the list
        response = client.get("/activities")
        participants = response.json()[activity]["participants"]
        for email in emails:
            assert email in participants
        
        # Remove one participant
        client.delete(f"/activities/{activity}/unregister?email={emails[0]}")
        
        # Verify removal
        response = client.get("/activities")
        participants = response.json()[activity]["participants"]
        assert emails[0] not in participants
        assert emails[1] in participants
        assert emails[2] in participants
