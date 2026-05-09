import pytest
from fastapi.testclient import TestClient
from main import app
from retrieval import store, load_index

# Ensure index is loaded before tests
load_index()

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_chat_schema_empty():
    response = client.post("/chat", json={"messages": []})
    assert response.status_code == 422

def test_chat_schema_valid():
    # Use a dummy message
    response = client.post("/chat", json={"messages": [{"role": "user", "content": "hello"}]})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "recommendations" in data
    assert "end_of_conversation" in data
    assert isinstance(data["recommendations"], list)
