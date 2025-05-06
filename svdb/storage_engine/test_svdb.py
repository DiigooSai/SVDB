#!/usr/bin/env python3
"""
Simple test script for SVDB storage engine
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / "python"))

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
    verify_file_integrity,
    calculate_file_hash,
)

def run_tests():
    print("Running SVDB Core tests...")
    
    # Create temp directory for tests
    test_dir = tempfile.mkdtemp()
    db_path = os.path.join(test_dir, "db")
    os.makedirs(db_path, exist_ok=True)
    
    try:
        # Test data
        test_data = b"Hello, SVDB! This is a test file."
        print(f"Test data: {test_data}")
        
        # Test hash calculation
        hash_val = calculate_hash(test_data)
        print(f"Hash (blake3): {hash_val}")
        
        # Test different hash algorithms
        hash1 = calculate_hash_with_algorithm(test_data, HASH_ALGORITHM_BLAKE3)
        hash2 = calculate_hash_with_algorithm(test_data, HASH_ALGORITHM_BLAKE2B)
        hash3 = calculate_hash_with_algorithm(test_data, HASH_ALGORITHM_KECCAK256)
        print(f"Blake3 hash: {hash1}")
        print(f"Blake2b hash: {hash2}")
        print(f"Keccak256 hash: {hash3}")
        
        # Test storage and retrieval
        print("\nTesting storage and retrieval...")
        stored_hash = store_file(db_path, test_data)
        print(f"Stored file with hash: {stored_hash}")
        
        retrieved_data = retrieve_file(db_path, stored_hash)
        print(f"Retrieved data: {retrieved_data}")
        
        if retrieved_data == test_data:
            print("✅ Storage and retrieval successful!")
        else:
            print("❌ Storage and retrieval failed!")
            return False
        
        # Test file chunking
        print("\nTesting file chunking...")
        large_data = b"x" * 1000  # 1000 bytes
        chunked_hash = store_file_with_options(
            db_path,
            large_data,
            algorithm=HASH_ALGORITHM_BLAKE2B,
            chunk_size=100  # 100 byte chunks
        )
        print(f"Stored chunked file with hash: {chunked_hash}")
        
        retrieved_chunked = retrieve_file(db_path, chunked_hash)
        if len(retrieved_chunked) == 1000 and retrieved_chunked == large_data:
            print("✅ Chunked storage and retrieval successful!")
        else:
            print("❌ Chunked storage and retrieval failed!")
            return False
        
        # Test file integrity verification
        print("\nTesting file integrity verification...")
        integrity_result = verify_file_integrity(db_path, stored_hash)
        if integrity_result:
            print("✅ File integrity verified!")
        else:
            print("❌ File integrity verification failed!")
            return False
        
        # Test path-based functions
        print("\nTesting file path functions...")
        test_file_path = os.path.join(test_dir, "test_file.txt")
        with open(test_file_path, "wb") as f:
            f.write(test_data)
        
        path_hash = store_file_from_path(db_path, test_file_path)
        print(f"Stored file from path with hash: {path_hash}")
        
        output_path = os.path.join(test_dir, "retrieved.txt")
        retrieve_file_to_path(db_path, path_hash, output_path)
        
        with open(output_path, "rb") as f:
            path_retrieved = f.read()
        
        if path_retrieved == test_data:
            print("✅ Path-based storage and retrieval successful!")
        else:
            print("❌ Path-based storage and retrieval failed!")
            return False
        
        print("\nAll tests passed successfully! ✅")
        return True
        
    finally:
        # Clean up
        shutil.rmtree(test_dir)

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1) 