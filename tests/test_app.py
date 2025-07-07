import pytest
import json
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

class TestHealthCheck:
    def test_healthcheck_endpoint(self):
        """Test the health check endpoint"""
        response = client.get("/healthcheck")
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["status"] == "healthy"
        assert response_data["code"] == 200
        assert "environment" in response_data
        assert "region" in response_data

class TestHelloEndpoint:
    @patch('app.get_api_key')
    def test_hello_with_valid_api_key(self, mock_get_api_key):
        """Test hello endpoint with valid API key"""
        # Mock get_api_key to return expected key
        mock_get_api_key.return_value = 'bijonguha'
        
        response = client.post(
            "/hello",
            json={"name": "Bijon"},
            headers={"X-API-Key": "bijonguha"}
        )
        
        assert response.status_code == 200
        assert response.json() == {"message": "Hello Bijon!"}

    @patch('app.get_api_key')
    def test_hello_with_invalid_api_key(self, mock_get_api_key):
        """Test hello endpoint with invalid API key"""
        # Mock get_api_key to return expected key
        mock_get_api_key.return_value = 'bijonguha'
        
        response = client.post(
            "/hello",
            json={"name": "Bijon"},
            headers={"X-API-Key": "invalid-key"}
        )
        
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_hello_without_api_key(self):
        """Test hello endpoint without API key"""
        response = client.post(
            "/hello",
            json={"name": "Bijon"}
        )
        
        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    @patch('app.get_api_key')
    def test_hello_with_api_key_error(self, mock_get_api_key):
        """Test hello endpoint when get_api_key fails"""
        # Mock get_api_key to raise an exception
        mock_get_api_key.side_effect = Exception("API Key Error")
        
        response = client.post(
            "/hello",
            json={"name": "Bijon"},
            headers={"X-API-Key": "bijonguha"}
        )
        
        assert response.status_code == 500

    @patch('app.get_api_key')
    def test_hello_with_missing_name(self, mock_get_api_key):
        """Test hello endpoint with missing name in request body"""
        # Mock get_api_key to return expected key
        mock_get_api_key.return_value = 'bijonguha'
        
        response = client.post(
            "/hello",
            json={},  # Missing name field
            headers={"X-API-Key": "bijonguha"}
        )
        
        assert response.status_code == 422  # Validation error

    @patch('app.get_api_key')
    def test_hello_with_empty_name(self, mock_get_api_key):
        """Test hello endpoint with empty name"""
        # Mock get_api_key to return expected key
        mock_get_api_key.return_value = 'bijonguha'
        
        response = client.post(
            "/hello",
            json={"name": ""},
            headers={"X-API-Key": "bijonguha"}
        )
        
        assert response.status_code == 200
        assert response.json() == {"message": "Hello !"}

class TestAPIKeyValidation:
    @patch('app.ssm_client')
    @patch('app.ENVIRONMENT', 'CLOUD-DEV')
    def test_get_api_key_from_parameter_store_success(self, mock_ssm):
        """Test successful API key retrieval from parameter store"""
        mock_ssm.get_parameter.return_value = {
            'Parameter': {'Value': 'test-key'}
        }
        
        from app import get_api_key
        result = get_api_key()
        
        assert result == 'test-key'
        mock_ssm.get_parameter.assert_called_once_with(
            Name='API_KEY',
            WithDecryption=True
        )

    @patch('app.ssm_client')
    @patch('app.ENVIRONMENT', 'CLOUD-DEV')
    @patch.dict(os.environ, {}, clear=True)  # Clear environment variables
    def test_get_api_key_from_parameter_store_failure(self, mock_ssm):
        """Test API key retrieval failure from parameter store with no fallback"""
        from botocore.exceptions import ClientError
        mock_ssm.get_parameter.side_effect = ClientError(
            {'Error': {'Code': 'ParameterNotFound'}}, 'GetParameter'
        )
        
        from app import get_api_key
        
        with pytest.raises(Exception):  # Should raise HTTPException when both SSM and env var fail
            get_api_key()

    @patch('app.ENVIRONMENT', 'LOCAL')
    @patch.dict(os.environ, {'API_KEY': 'local-test-key'})
    def test_get_api_key_local_environment(self):
        """Test API key retrieval in LOCAL environment"""
        from app import get_api_key
        result = get_api_key()
        
        assert result == 'local-test-key'

class TestInfoEndpoint:
    def test_info_endpoint(self):
        """Test the info endpoint"""
        response = client.get("/info")
        assert response.status_code == 200
        response_data = response.json()
        assert "environment" in response_data
        assert "aws_region" in response_data
        assert "title" in response_data
        assert "version" in response_data

class TestDocumentation:
    def test_openapi_docs_accessible(self):
        """Test that OpenAPI docs are accessible"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_json_accessible(self):
        """Test that OpenAPI JSON is accessible"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        assert "openapi" in response.json()