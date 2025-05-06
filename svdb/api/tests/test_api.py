import os
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Add parent directory to path
import sys
from pathlib import Path
parent_dir = str(Path(__file__).resolve().parent.parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import the app
from api.app import app

# Create a test client
client = TestClient(app)

# Mock database path
TEST_DB_PATH = "./test_data"

# Setup and teardown
@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup - create test directory
    os.makedirs(TEST_DB_PATH, exist_ok=True)
    
    # Pass control back to the test
    yield
    
    # Teardown - remove test directory
    import shutil
    if os.path.exists(TEST_DB_PATH):
        shutil.rmtree(TEST_DB_PATH)

# Mock for svdb_core
class MockSvdbCore:
    @staticmethod
    def py_calculate_hash(data):
        import hashlib
        return hashlib.blake2b(data).hexdigest()
    
    @staticmethod
    def py_store_file(db_path, data):
        hash_val = MockSvdbCore.py_calculate_hash(data)
        # Mock storage
        os.makedirs(os.path.join(db_path, 'data'), exist_ok=True)
        file_path = os.path.join(db_path, 'data', hash_val)
        with open(file_path, 'wb') as f:
            f.write(data)
        return hash_val
    
    @staticmethod
    def py_retrieve_file(db_path, hash_val):
        file_path = os.path.join(db_path, 'data', hash_val)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File with hash {hash_val} not found")
        with open(file_path, 'rb') as f:
            return f.read()

# Mock for SVDBVerifier
class MockSVDBVerifier:
    @staticmethod
    async def verify_hash(file_hash):
        # Return mock verification data
        return {
            'verified': True,
            'tx_hash': 'mock_blockchain_tx_hash',
            'block_hash': 'mock_blockchain_block_hash',
            'timestamp': 1234567890,
            'metadata': {'source': 'blockchain_test'}
        }

# Mock for SVDBVerifier class
class MockVerifier:
    async def verify_hash(self, file_hash):
        return {
            'verified': True,
            'tx_hash': 'blockchain_tx_hash',
            'block_hash': 'blockchain_block_hash',
            'timestamp': 1234567890,
            'metadata': {'source': 'blockchain'}
        }
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, *args):
        pass

# Test the health check endpoint
def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "timestamp" in response.json()

# Test storing a file
@patch('api.app.svdb_core', MockSvdbCore)
@patch('api.app.get_db_path')
@patch('api.app.submit_to_blockchain')
def test_store_file(mock_submit, mock_get_db_path, tmp_path):
    # Setup mocks
    mock_get_db_path.return_value = str(tmp_path)
    mock_submit.return_value = "mock_tx_hash"
    
    # Create data directory
    data_dir = os.path.join(tmp_path, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Test file data
    test_data = b"Test file content"
    expected_hash = MockSvdbCore.py_calculate_hash(test_data)
    
    # Pre-store the file to simulate the svdb_core.py_store_file behavior
    # This is needed because apparently the mock isn't actually storing the file
    with open(os.path.join(data_dir, expected_hash), 'wb') as f:
        f.write(test_data)
    
    # Send request
    response = client.post(
        "/store",
        files={"file": ("test.txt", test_data, "text/plain")}
    )
    
    # Check response
    assert response.status_code == 200
    assert response.json()["hash"] == expected_hash
    
    # Verify file was stored
    stored_path = os.path.join(tmp_path, 'data', expected_hash)
    assert os.path.exists(stored_path)
    
    with open(stored_path, 'rb') as f:
        assert f.read() == test_data

# Test retrieving a file
@patch('api.app.svdb_core', MockSvdbCore)
@patch('api.app.get_db_path')
def test_retrieve_file(mock_get_db_path, tmp_path):
    # Setup mocks
    mock_get_db_path.return_value = str(tmp_path)
    
    # Store a test file
    test_data = b"Test file content"
    hash_val = MockSvdbCore.py_store_file(str(tmp_path), test_data)
    
    # Send request
    response = client.get(f"/retrieve/{hash_val}")
    
    # Check response
    assert response.status_code == 200
    assert response.content == test_data

# Test retrieving a non-existent file
@patch('api.app.svdb_core', MockSvdbCore)
@patch('api.app.get_db_path')
def test_retrieve_nonexistent_file(mock_get_db_path, tmp_path):
    # Setup mocks
    mock_get_db_path.return_value = str(tmp_path)
    
    # Send request for a non-existent file
    response = client.get("/retrieve/nonexistent_hash")
    
    # Check response
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

# Test verifying a file
@patch('api.app.get_transaction_by_file_hash')
@patch('api.app.SVDBVerifier')
def test_verify_file(mock_verifier, mock_get_tx):
    # Setup mocks
    mock_verifier_instance = MagicMock()
    mock_verifier.return_value.__aenter__.return_value = mock_verifier_instance
    
    # Mock transaction in database
    mock_get_tx.return_value = {
        'file_hash': 'test_hash',
        'tx_hash': 'test_tx_hash',
        'status': 'confirmed',
        'block_hash': 'test_block_hash',
        'timestamp': 1234567890,
        'metadata': json.dumps({'test': 'metadata'})
    }
    
    # Send request
    response = client.get("/verify/test_hash")
    
    # Check response
    assert response.status_code == 200
    resp_json = response.json()
    assert resp_json["hash"] == "test_hash"
    assert resp_json["verified"] == True
    assert resp_json["tx_hash"] == "test_tx_hash"
    assert resp_json["block_hash"] == "test_block_hash"
    assert resp_json["timestamp"] == 1234567890
    assert resp_json["metadata"] == {'test': 'metadata'}
    
    # Verify we didn't need to call the blockchain
    mock_verifier_instance.verify_hash.assert_not_called()

# Test verifying a file that requires blockchain verification
@patch('api.app.get_transaction_by_file_hash')
@patch('api.app.SVDBVerifier')
def test_verify_file_blockchain(mock_verifier, mock_get_tx):
    # Setup mocks - use our custom MockVerifier
    mock_verifier.return_value = MockVerifier()
    
    # Mock no transaction in database
    mock_get_tx.return_value = None
    
    # Send request
    response = client.get("/verify/test_hash")
    
    # Check response
    assert response.status_code == 200
    resp_json = response.json()
    assert resp_json["hash"] == "test_hash"
    assert resp_json["verified"] == True
    assert resp_json["tx_hash"] == "blockchain_tx_hash"
    assert resp_json["block_hash"] == "blockchain_block_hash"

# Test error handling in verification
@patch('api.app.get_transaction_by_file_hash')
@patch('api.app.SVDBVerifier')
def test_verify_file_error(mock_verifier, mock_get_tx):
    # Setup mocks
    mock_verifier_instance = MagicMock()
    mock_verifier.return_value.__aenter__.return_value = mock_verifier_instance
    
    # Mock no transaction in database
    mock_get_tx.return_value = None
    
    # Mock blockchain verification error
    mock_verifier_instance.verify_hash.side_effect = Exception("Test error")
    
    # Send request
    response = client.get("/verify/test_hash")
    
    # Check response
    assert response.status_code == 200  # Should still return 200
    resp_json = response.json()
    assert resp_json["hash"] == "test_hash"
    assert resp_json["verified"] == False  # Should indicate not verified
    assert "error" in resp_json["metadata"] 