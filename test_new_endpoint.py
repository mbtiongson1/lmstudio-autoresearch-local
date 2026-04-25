from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)

@patch('app.main.lm_client.list_models')
def test_get_models_endpoint(mock_list):
    mock_list.return_value = {"models": [{"key": "test"}]}
    response = client.get("/api/models")
    assert response.status_code == 200
    assert response.json() == {"models": [{"key": "test"}]}

test_get_models_endpoint()
print("Test passed!")
