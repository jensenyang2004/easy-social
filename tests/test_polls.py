import pytest
from conftest import register, logout

@pytest.mark.integration
def test_create_poll_post(client, app):
    register(client, "alice")
    
    poll_data = {
        "content": "What's your favourite stack?",
        "poll": {
            "options": ["Flask", "Django", "FastAPI", "Express"]
        }
    }
    
    response = client.post(
        "/api/posts",
        json=poll_data
    )
    
    assert response.status_code == 201
    data = response.get_json()
    assert data["body"] == poll_data["content"]
    assert "poll" in data
    assert len(data["poll"]["options"]) == 4
    assert data["poll"]["options"][0]["text"] == "Flask"


@pytest.mark.integration
def test_verify_poll_options_count(client, app):
    register(client, "alice")
    
    # 1 option
    response = client.post("/api/posts", json={
        "content": "Invalid",
        "poll": {"options": ["Only one"]}
    })
    assert response.status_code == 400
    assert b"between 2 and 4 options" in response.data
    
    # 5 options
    response = client.post("/api/posts", json={
        "content": "Invalid",
        "poll": {"options": ["1", "2", "3", "4", "5"]}
    })
    assert response.status_code == 400
    assert b"between 2 and 4 options" in response.data


@pytest.mark.integration
def test_cast_vote(client, app):
    register(client, "alice")
    resp = client.post("/api/posts", json={
        "content": "Vote test",
        "poll": {"options": ["A", "B"]}
    })
    poll_id = resp.get_json()["poll"]["id"]
    option_id = resp.get_json()["poll"]["options"][0]["id"]
    
    # Vote as alice
    response = client.post(f"/api/polls/{poll_id}/vote", json={
        "option_id": option_id
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    # Results should be sorted by order or consistent
    assert any(r["option_id"] == option_id and r["votes"] == 1 for r in data["results"])


@pytest.mark.integration
def test_duplicate_vote_rejected(client, app):
    register(client, "alice")
    resp = client.post("/api/posts", json={
        "content": "Duplicate vote test",
        "poll": {"options": ["A", "B"]}
    })
    poll_id = resp.get_json()["poll"]["id"]
    option_id = resp.get_json()["poll"]["options"][0]["id"]
    
    # First vote
    client.post(f"/api/polls/{poll_id}/vote", json={"option_id": option_id})
    
    # Second vote
    response = client.post(f"/api/polls/{poll_id}/vote", json={"option_id": option_id})
    assert response.status_code == 409
    assert b"already voted" in response.data

@pytest.mark.integration
def test_invalid_option_rejected(client, app):
    register(client, "alice")
    # Poll 1
    resp1 = client.post("/api/posts", json={"content": "P1", "poll": {"options": ["A", "B"]}})
    poll1_id = resp1.get_json()["poll"]["id"]
    
    # Poll 2
    resp2 = client.post("/api/posts", json={"content": "P2", "poll": {"options": ["C", "D"]}})
    poll2_id = resp2.get_json()["poll"]["id"]
    optC_id = resp2.get_json()["poll"]["options"][0]["id"]
    
    # Try voting on Poll 1 with Option C (from Poll 2)
    response = client.post(f"/api/polls/{poll1_id}/vote", json={"option_id": optC_id})
    assert response.status_code == 400
    assert b"belong to this poll" in response.data

@pytest.mark.integration
def test_get_results(client, app):
    # Setup: Create poll and have two users vote
    register(client, "alice")
    resp = client.post("/api/posts", json={"content": "Results test", "poll": {"options": ["A", "B"]}})
    poll_id = resp.get_json()["poll"]["id"]
    optA_id = resp.get_json()["poll"]["options"][0]["id"]
    optB_id = resp.get_json()["poll"]["options"][1]["id"]
    
    # Alice votes A
    client.post(f"/api/polls/{poll_id}/vote", json={"option_id": optA_id})
    logout(client)
    
    # Bob votes B
    register(client, "bob")
    client.post(f"/api/polls/{poll_id}/vote", json={"option_id": optB_id})
    
    # Get results
    response = client.get(f"/api/polls/{poll_id}/results")
    assert response.status_code == 200
    data = response.get_json()
    assert data["user_voted_option_id"] == optB_id
    assert len(data["results"]) == 2
    for r in data["results"]:
        assert r["votes"] == 1
        assert r["percentage"] == 50.0

@pytest.mark.unit
def test_vote_percentage_calculation(app):
    from easy_social.models import Poll, PollOption, PollVote
    
    with app.app_context():
        poll = Poll(id="p1")
        o1 = PollOption(id="o1", poll=poll, text="A", order=0)
        o2 = PollOption(id="o2", poll=poll, text="B", order=1)
        poll.options = [o1, o2]
        
        # 2 votes for o1, 1 for o2
        poll.votes = [
            PollVote(poll=poll, option=o1, option_id="o1", user_id=1),
            PollVote(poll=poll, option=o1, option_id="o1", user_id=2),
            PollVote(poll=poll, option=o2, option_id="o2", user_id=3)
        ]
        
        results = poll.get_results()
        r1 = next(r for r in results if r["option_id"] == "o1")
        r2 = next(r for r in results if r["option_id"] == "o2")
        
        assert r1["votes"] == 2
        assert r1["percentage"] == 66.7
        assert r2["votes"] == 1
        assert r2["percentage"] == 33.3
