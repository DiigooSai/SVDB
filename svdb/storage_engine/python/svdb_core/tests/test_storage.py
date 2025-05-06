import os
import shutil
import tempfile
import unittest
from pathlib import Path

try:
    # Try absolute import first
    from svdb_core import (
        calculate_hash,
        calculate_hash_with_algorithm,
        store_file,
        store_file_with_options,
        retrieve_file,
        HASH_ALGORITHM_BLAKE3,
        HASH_ALGORITHM_BLAKE2B,
        HASH_ALGORITHM_KECCAK256,
    )
    from svdb_core.helpers import (
        store_file_from_path,
        retrieve_file_to_path,
        batch_store_files,
        verify_file_integrity,
        calculate_file_hash,
    )
except ImportError:
    # Fall back to relative import
    from ... import (
        calculate_hash,
        calculate_hash_with_algorithm,
        store_file,
        store_file_with_options,
        retrieve_file,
        HASH_ALGORITHM_BLAKE3,
        HASH_ALGORITHM_BLAKE2B,
        HASH_ALGORITHM_KECCAK256,
    )
    from ...helpers import (
        store_file_from_path,
        retrieve_file_to_path,
        batch_store_files,
        verify_file_integrity,
        calculate_file_hash,
    )


class TestStorageEngine(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "db")
        os.makedirs(self.db_path, exist_ok=True)
        
        # Create a test file
        self.test_file_path = os.path.join(self.test_dir, "test_file.txt")
        self.test_data = b"Hello, SVDB! This is a test file."
        with open(self.test_file_path, "wb") as f:
            f.write(self.test_data)
    
    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)
    
    def test_calculate_hash(self):
        # Test basic hash calculation
        hash_val = calculate_hash(self.test_data)
        self.assertIsInstance(hash_val, str)
        self.assertTrue(len(hash_val) > 0)
    
    def test_calculate_hash_with_algorithm(self):
        # Test hash calculation with different algorithms
        hash1 = calculate_hash_with_algorithm(self.test_data, HASH_ALGORITHM_BLAKE3)
        hash2 = calculate_hash_with_algorithm(self.test_data, HASH_ALGORITHM_BLAKE2B)
        hash3 = calculate_hash_with_algorithm(self.test_data, HASH_ALGORITHM_KECCAK256)
        
        # Verify we get different hashes with different algorithms
        self.assertNotEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)
        self.assertNotEqual(hash2, hash3)
    
    def test_store_and_retrieve(self):
        # Store a file
        hash_val = store_file(self.db_path, self.test_data)
        
        # Retrieve the file
        retrieved_data = retrieve_file(self.db_path, hash_val)
        
        # Verify the data is the same
        self.assertEqual(retrieved_data, self.test_data)
    
    def test_store_with_options(self):
        # Test storing with different options
        hash_val = store_file_with_options(
            self.db_path, 
            self.test_data, 
            algorithm=HASH_ALGORITHM_BLAKE2B,
            chunk_size=10  # Small chunk size for testing
        )
        
        # Retrieve and verify
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, self.test_data)
    
    def test_helper_functions(self):
        # Test storing from path
        hash_val = store_file_from_path(self.db_path, self.test_file_path)
        
        # Test retrieving to path
        output_path = os.path.join(self.test_dir, "retrieved.txt")
        retrieve_file_to_path(self.db_path, hash_val, output_path)
        
        # Verify the file was correctly retrieved
        with open(output_path, "rb") as f:
            retrieved_data = f.read()
        self.assertEqual(retrieved_data, self.test_data)
    
    def test_verify_integrity(self):
        # Store a file
        hash_val = store_file(self.db_path, self.test_data)
        
        # Verify integrity
        self.assertTrue(verify_file_integrity(self.db_path, hash_val))
        
        # Test with invalid hash
        self.assertFalse(verify_file_integrity(self.db_path, "invalid_hash"))
    
    def test_batch_store(self):
        # Create additional test files
        test_file2 = os.path.join(self.test_dir, "test_file2.txt")
        with open(test_file2, "wb") as f:
            f.write(b"Second test file")
        
        test_file3 = os.path.join(self.test_dir, "test_file3.txt")
        with open(test_file3, "wb") as f:
            f.write(b"Third test file")
        
        # Batch store files
        results = batch_store_files(
            self.db_path, 
            [self.test_file_path, test_file2, test_file3]
        )
        
        # Verify all files were stored
        self.assertEqual(len(results), 3)
        
        # Verify each file can be retrieved
        for file_path, hash_val in results.items():
            with open(file_path, "rb") as f:
                original_data = f.read()
            
            retrieved_data = retrieve_file(self.db_path, hash_val)
            self.assertEqual(retrieved_data, original_data)
    
    def test_chunking(self):
        # Create a larger file for chunking
        large_data = b"x" * 1000  # 1000 bytes
        large_file_path = os.path.join(self.test_dir, "large_file.bin")
        with open(large_file_path, "wb") as f:
            f.write(large_data)
        
        # Store with small chunks
        hash_val = store_file_with_options(
            self.db_path,
            large_data,
            chunk_size=100  # 100 byte chunks
        )
        
        # Retrieve and verify
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, large_data)


if __name__ == "__main__":
    unittest.main() 