"""Unit tests for Model Management API endpoints"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
from app.main import app

client = TestClient(app)

class TestModelManagementAPI:
    """Test model management routes."""

    @patch('app.main.lm_client.list_models')
    def test_get_models(self, mock_list):
        """Test listing models."""
        mock_response = {
            "models": [
                {
                    "type": "llm",
                    "publisher": "test-publisher",
                    "key": "test-model-key",
                    "display_name": "Test Model",
                    "architecture": "llama",
                    "quantization": {"name": "Q4_K_M", "bits_per_weight": 4},
                    "size_bytes": 1024,
                    "params_string": "7B",
                    "loaded_instances": [],
                    "max_context_length": 4096,
                    "format": "gguf",
                    "capabilities": {"vision": False, "trained_for_tool_use": False},
                    "description": "A test model"
                }
            ]
        }
        mock_list.return_value = mock_response
        
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert len(data["models"]) == 1
        assert data["models"][0]["key"] == "test-model-key"

    @patch('app.main.lm_client.load_model')
    def test_load_model(self, mock_load):
        """Test loading a model."""
        mock_response = {
            "type": "llm",
            "instance_id": "test-model-key",
            "load_time_seconds": 1.5,
            "status": "loaded"
        }
        mock_load.return_value = mock_response
        
        payload = {"model": "test-model-key", "context_length": 2048}
        response = client.post("/api/models/load", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["instance_id"] == "test-model-key"
        assert data["status"] == "loaded"

    @patch('app.main.lm_client.unload_model')
    def test_unload_model(self, mock_unload):
        """Test unloading a model."""
        mock_response = {"instance_id": "test-instance-id"}
        mock_unload.return_value = mock_response
        
        payload = {"instance_id": "test-instance-id"}
        response = client.post("/api/models/unload", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["instance_id"] == "test-instance-id"
