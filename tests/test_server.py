"""Integration tests for FastAPI local REST server."""

from fastapi.testclient import TestClient

from server.app import app

client = TestClient(app)


def test_healthz_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "active_pack" in data
    assert "installed_packs" in data


def test_list_packs_endpoint():
    response = client.get("/v1/packs")
    assert response.status_code == 200
    data = response.json()
    assert "packs" in data
    assert len(data["packs"]) >= 1


def test_ask_endpoint():
    payload = {
        "question": "Can a player be in an offside position directly from a throw-in?",
        "history": [],
    }
    response = client.post("/v1/ask", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "citations" in data
    assert "status" in data
    assert "latencies" in data


def test_chunk_retrieval_endpoint():
    # Retrieve law11-1
    response = client.get("/v1/chunks/law11-1")
    assert response.status_code == 200
    data = response.json()
    assert data["chunk_id"] == "law11-1"
    assert "text" in data

    # Nonexistent chunk
    response404 = client.get("/v1/chunks/nonexistent-999")
    assert response404.status_code == 404


def test_feedback_endpoint():
    payload = {
        "query": "Is this offside?",
        "answer": "No [C1]",
        "rating": 1,
        "comment": "Accurate answer",
    }
    response = client.post("/v1/feedback", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
