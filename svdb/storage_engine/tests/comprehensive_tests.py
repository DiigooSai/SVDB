#!/usr/bin/env python3
"""
Comprehensive Test Suite for SVDB Storage Engine
"""
import os
import sys
import time
import shutil
import random
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

try:
    from svdb_core import (
        calculate_hash,
        calculate_hash_with_algorithm,
        store_file,
        store_file_with_options,
        retrieve_file,
        HASH_ALGORITHM_BLAKE3,
        HASH_ALGORITHM_BLAKE2B,
        HASH_ALGORITHM_KECCAK256,
        DEFAULT_CHUNK_SIZE,
        HAS_RUST_CORE,
    )
    from svdb_core.helpers import (
        store_file_from_path,
        retrieve_file_to_path,
        batch_store_files,
        verify_file_integrity,
        calculate_file_hash,
        stream_store_file,
        list_files_by_hash_prefix,
    )
except ImportError as e:
    print(f"Failed to import svdb_core: {e}")
    print("Make sure you've installed the package correctly.")
    sys.exit(1)

class BasicFunctionalityTests(unittest.TestCase):
    """Basic functionality tests for the SVDB Storage Engine"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "db")
        os.makedirs(self.db_path, exist_ok=True)
        self.test_data = b"Hello, SVDB! Basic test data."
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_hash_calculation(self):
        """Test hash calculation with different algorithms"""
        hash1 = calculate_hash(self.test_data)
        self.assertIsInstance(hash1, str)
        self.assertTrue(len(hash1) > 0)
        
        # Hashing should be deterministic
        hash2 = calculate_hash(self.test_data)
        self.assertEqual(hash1, hash2)
        
        # Different algorithms should produce different hashes
        hash_blake3 = calculate_hash_with_algorithm(self.test_data, HASH_ALGORITHM_BLAKE3)
        hash_blake2b = calculate_hash_with_algorithm(self.test_data, HASH_ALGORITHM_BLAKE2B)
        hash_keccak = calculate_hash_with_algorithm(self.test_data, HASH_ALGORITHM_KECCAK256)
        
        # In fallback mode, Blake3 uses Blake2b implementation, so they'll be identical
        if not HAS_RUST_CORE:
            print("  - Note: Using Python fallback, skipping Blake3 vs Blake2b comparison")
        else:
            self.assertNotEqual(hash_blake3, hash_blake2b)
            
        # These should always be different
        self.assertNotEqual(hash_blake3, hash_keccak)
        self.assertNotEqual(hash_blake2b, hash_keccak)
    
    def test_store_retrieve(self):
        """Test basic store and retrieve operations"""
        hash_val = store_file(self.db_path, self.test_data)
        self.assertIsInstance(hash_val, str)
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, self.test_data)
    
    def test_non_existent_hash(self):
        """Test retrieving a non-existent hash"""
        with self.assertRaises(Exception):
            retrieve_file(self.db_path, "nonexistenthash")


class ChunkingTests(unittest.TestCase):
    """Tests for file chunking functionality"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "db")
        os.makedirs(self.db_path, exist_ok=True)
        
        # Create different sized test data
        self.small_data = b"x" * 500  # 500 bytes
        self.medium_data = b"y" * 5000  # 5 KB
        self.large_data = b"z" * 50000  # 50 KB
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_no_chunking(self):
        """Test storage without chunking"""
        hash_val = store_file_with_options(
            self.db_path, 
            self.small_data, 
            algorithm=HASH_ALGORITHM_BLAKE3,
            chunk_size=0  # No chunking
        )
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, self.small_data)
    
    def test_small_chunks(self):
        """Test storage with small chunks"""
        hash_val = store_file_with_options(
            self.db_path, 
            self.medium_data, 
            algorithm=HASH_ALGORITHM_BLAKE3,
            chunk_size=1000  # 1 KB chunks
        )
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, self.medium_data)
    
    def test_large_chunks(self):
        """Test storage with large chunks"""
        hash_val = store_file_with_options(
            self.db_path, 
            self.large_data, 
            algorithm=HASH_ALGORITHM_BLAKE3,
            chunk_size=10000  # 10 KB chunks
        )
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, self.large_data)
    
    def test_extremely_small_chunks(self):
        """Test storage with extremely small chunks"""
        hash_val = store_file_with_options(
            self.db_path, 
            self.medium_data, 
            algorithm=HASH_ALGORITHM_BLAKE3,
            chunk_size=10  # 10 byte chunks (very small)
        )
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, self.medium_data)
        

class AlgorithmTests(unittest.TestCase):
    """Tests for different hashing algorithms"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "db")
        os.makedirs(self.db_path, exist_ok=True)
        self.test_data = b"Testing different hash algorithms"
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_blake3(self):
        """Test storage and retrieval with Blake3"""
        hash_val = store_file_with_options(
            self.db_path, 
            self.test_data, 
            algorithm=HASH_ALGORITHM_BLAKE3
        )
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, self.test_data)
    
    def test_blake2b(self):
        """Test storage and retrieval with Blake2b"""
        hash_val = store_file_with_options(
            self.db_path, 
            self.test_data, 
            algorithm=HASH_ALGORITHM_BLAKE2B
        )
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, self.test_data)
    
    def test_keccak256(self):
        """Test storage and retrieval with Keccak256"""
        hash_val = store_file_with_options(
            self.db_path, 
            self.test_data, 
            algorithm=HASH_ALGORITHM_KECCAK256
        )
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, self.test_data)


class HelperFunctionsTests(unittest.TestCase):
    """Tests for helper functions"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "db")
        os.makedirs(self.db_path, exist_ok=True)
        
        # Create test files
        self.test_file_path = os.path.join(self.test_dir, "test_file.txt")
        with open(self.test_file_path, "wb") as f:
            f.write(b"Helper functions test data")
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_store_from_path(self):
        """Test storing from a file path"""
        hash_val = store_file_from_path(self.db_path, self.test_file_path)
        
        # Retrieve and verify
        with open(self.test_file_path, "rb") as f:
            original_data = f.read()
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, original_data)
    
    def test_retrieve_to_path(self):
        """Test retrieving to a file path"""
        # First store a file
        with open(self.test_file_path, "rb") as f:
            original_data = f.read()
        
        hash_val = store_file(self.db_path, original_data)
        
        # Now retrieve to a different path
        output_path = os.path.join(self.test_dir, "retrieved.txt")
        retrieve_file_to_path(self.db_path, hash_val, output_path)
        
        # Verify the content
        with open(output_path, "rb") as f:
            retrieved_data = f.read()
        
        self.assertEqual(retrieved_data, original_data)
    
    def test_batch_store(self):
        """Test batch storing multiple files"""
        # Create additional test files
        file_paths = []
        original_data = {}
        
        for i in range(5):
            file_path = os.path.join(self.test_dir, f"test_file_{i}.txt")
            data = f"Batch test file {i}".encode()
            with open(file_path, "wb") as f:
                f.write(data)
            file_paths.append(file_path)
            original_data[file_path] = data
        
        # Batch store files
        results = batch_store_files(self.db_path, file_paths)
        
        # Verify all files were stored successfully
        self.assertEqual(len(results), len(file_paths))
        
        # Verify each file can be retrieved correctly
        for file_path, hash_val in results.items():
            retrieved_data = retrieve_file(self.db_path, hash_val)
            self.assertEqual(retrieved_data, original_data[file_path])
    
    def test_verify_integrity(self):
        """Test file integrity verification"""
        # Store a file
        with open(self.test_file_path, "rb") as f:
            original_data = f.read()
        
        hash_val = store_file(self.db_path, original_data)
        
        # Verify integrity
        result = verify_file_integrity(self.db_path, hash_val)
        self.assertTrue(result)
        
        # Test with invalid hash
        result = verify_file_integrity(self.db_path, "invalid_hash")
        self.assertFalse(result)
    
    def test_stream_store(self):
        """Test streaming storage of a file"""
        # Create a large test file
        large_file_path = os.path.join(self.test_dir, "large_file.bin")
        with open(large_file_path, "wb") as f:
            f.write(b"x" * 10000)  # 10 KB
        
        # Stream store the file
        with open(large_file_path, "rb") as f:
            hash_val = stream_store_file(self.db_path, f)
        
        # Verify the content
        with open(large_file_path, "rb") as f:
            original_data = f.read()
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, original_data)


class StressTests(unittest.TestCase):
    """Stress tests for the storage engine"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "db")
        os.makedirs(self.db_path, exist_ok=True)
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_many_small_files(self):
        """Test storing and retrieving many small files"""
        num_files = 100
        size = 100  # 100 bytes
        
        # Store files
        hash_values = []
        original_data = []
        
        for i in range(num_files):
            data = f"Small file {i}".encode() + b"x" * (size - 15)
            original_data.append(data)
            hash_val = store_file(self.db_path, data)
            hash_values.append(hash_val)
        
        # Retrieve and verify all files
        for i, hash_val in enumerate(hash_values):
            retrieved_data = retrieve_file(self.db_path, hash_val)
            self.assertEqual(retrieved_data, original_data[i])
    
    def test_large_file(self):
        """Test storing and retrieving a large file"""
        # 10 MB file
        size = 10 * 1024 * 1024
        data = b"x" * size
        
        # Store file with chunking
        hash_val = store_file_with_options(
            self.db_path,
            data,
            chunk_size=1024 * 1024  # 1 MB chunks
        )
        
        # Retrieve and verify
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(len(retrieved_data), size)
        self.assertEqual(retrieved_data, data)
    
    def test_concurrent_operations(self):
        """Test concurrent store and retrieve operations"""
        num_operations = 20
        data_list = [f"Concurrent test {i}".encode() * 100 for i in range(num_operations)]
        hash_values = []
        
        # Store files concurrently
        def store_operation(data):
            return store_file(self.db_path, data)
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            hash_values = list(executor.map(store_operation, data_list))
        
        # Retrieve files concurrently
        def retrieve_operation(args):
            idx, hash_val = args
            data = retrieve_file(self.db_path, hash_val)
            return idx, data
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(retrieve_operation, enumerate(hash_values)))
        
        # Verify all files
        for idx, data in sorted(results):
            self.assertEqual(data, data_list[idx])


class EdgeCaseTests(unittest.TestCase):
    """Edge case tests for the storage engine"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "db")
        os.makedirs(self.db_path, exist_ok=True)
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_empty_file(self):
        """Test storing and retrieving an empty file"""
        empty_data = b""
        hash_val = store_file(self.db_path, empty_data)
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, empty_data)
    
    def test_binary_data(self):
        """Test storing and retrieving binary data"""
        binary_data = bytes([random.randint(0, 255) for _ in range(1000)])
        hash_val = store_file(self.db_path, binary_data)
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, binary_data)
    
    def test_unicode_data(self):
        """Test storing and retrieving Unicode data"""
        unicode_data = "こんにちは世界! Hello World! 👋🌍".encode("utf-8")
        hash_val = store_file(self.db_path, unicode_data)
        
        retrieved_data = retrieve_file(self.db_path, hash_val)
        self.assertEqual(retrieved_data, unicode_data)
    
    def test_same_content_different_algorithms(self):
        """Test storing the same content with different hash algorithms"""
        data = b"Same content, different algorithms"
        
        hash1 = store_file_with_options(self.db_path, data, algorithm=HASH_ALGORITHM_BLAKE3)
        hash2 = store_file_with_options(self.db_path, data, algorithm=HASH_ALGORITHM_BLAKE2B)
        hash3 = store_file_with_options(self.db_path, data, algorithm=HASH_ALGORITHM_KECCAK256)
        
        # In fallback mode, Blake3 uses Blake2b implementation, so they'll be identical
        if not HAS_RUST_CORE:
            print("  - Note: Using Python fallback, skipping Blake3 vs Blake2b comparison")
        else:
            # Hashes should be different
            self.assertNotEqual(hash1, hash2)
            
        # These should always be different
        self.assertNotEqual(hash1, hash3)
        self.assertNotEqual(hash2, hash3)
        
        # But content should be the same
        data1 = retrieve_file(self.db_path, hash1)
        data2 = retrieve_file(self.db_path, hash2)
        data3 = retrieve_file(self.db_path, hash3)
        
        self.assertEqual(data1, data)
        self.assertEqual(data2, data)
        self.assertEqual(data3, data)


class BenchmarkTests(unittest.TestCase):
    """Benchmark tests for the storage engine (not actual unit tests)"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "db")
        os.makedirs(self.db_path, exist_ok=True)
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_hash_performance(self):
        """Benchmark hash algorithm performance"""
        sizes = [1024, 1024*1024, 10*1024*1024]  # 1KB, 1MB, 10MB
        algorithms = [HASH_ALGORITHM_BLAKE3, HASH_ALGORITHM_BLAKE2B, HASH_ALGORITHM_KECCAK256]
        
        results = {}
        
        for size in sizes:
            data = b"x" * size
            size_results = {}
            
            for algo in algorithms:
                start_time = time.time()
                calculate_hash_with_algorithm(data, algo)
                end_time = time.time()
                
                size_results[algo] = end_time - start_time
            
            results[size] = size_results
        
        # Print results
        print("\nHash Algorithm Performance:")
        print(f"{'Size':<10} {'Blake3 (s)':<12} {'Blake2b (s)':<12} {'Keccak256 (s)':<12}")
        for size, algos in results.items():
            size_str = f"{size/1024:.0f}KB" if size < 1024*1024 else f"{size/(1024*1024):.0f}MB"
            print(f"{size_str:<10} {algos[HASH_ALGORITHM_BLAKE3]:<12.6f} {algos[HASH_ALGORITHM_BLAKE2B]:<12.6f} {algos[HASH_ALGORITHM_KECCAK256]:<12.6f}")
    
    def test_storage_retrieval_performance(self):
        """Benchmark storage and retrieval performance"""
        sizes = [1024, 1024*1024, 10*1024*1024]  # 1KB, 1MB, 10MB
        chunk_sizes = [0, 1024*1024]  # No chunking, 1MB chunks
        
        results = {}
        
        for size in sizes:
            data = b"x" * size
            size_results = {}
            
            for chunk_size in chunk_sizes:
                # Test storage
                start_time = time.time()
                hash_val = store_file_with_options(self.db_path, data, chunk_size=chunk_size)
                store_time = time.time() - start_time
                
                # Test retrieval
                start_time = time.time()
                retrieve_file(self.db_path, hash_val)
                retrieve_time = time.time() - start_time
                
                chunk_label = "No Chunking" if chunk_size == 0 else f"{chunk_size/1024:.0f}KB Chunks"
                size_results[chunk_label] = (store_time, retrieve_time)
            
            results[size] = size_results
        
        # Print results
        print("\nStorage and Retrieval Performance:")
        print(f"{'Size':<10} {'Method':<15} {'Store (s)':<12} {'Retrieve (s)':<12}")
        for size, chunks in results.items():
            size_str = f"{size/1024:.0f}KB" if size < 1024*1024 else f"{size/(1024*1024):.0f}MB"
            for chunk_label, (store_time, retrieve_time) in chunks.items():
                print(f"{size_str:<10} {chunk_label:<15} {store_time:<12.6f} {retrieve_time:<12.6f}")


def run_all_tests():
    """Run all tests with proper output formatting"""
    # Define test suites
    test_suites = [
        unittest.TestLoader().loadTestsFromTestCase(BasicFunctionalityTests),
        unittest.TestLoader().loadTestsFromTestCase(ChunkingTests),
        unittest.TestLoader().loadTestsFromTestCase(AlgorithmTests),
        unittest.TestLoader().loadTestsFromTestCase(HelperFunctionsTests),
        unittest.TestLoader().loadTestsFromTestCase(StressTests),
        unittest.TestLoader().loadTestsFromTestCase(EdgeCaseTests),
        unittest.TestLoader().loadTestsFromTestCase(BenchmarkTests),
    ]
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    
    print("=" * 80)
    print(f"SVDB Storage Engine Comprehensive Tests")
    print(f"Running tests at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    results = []
    
    for suite in test_suites:
        print(f"\nRunning {suite.countTestCases()} tests from {suite._tests[0].__class__.__name__}")
        print("-" * 80)
        result = runner.run(suite)
        results.append((suite._tests[0].__class__.__name__, result))
        print("-" * 80)
    
    # Print summary
    print("\n" + "=" * 80)
    print("Test Summary:")
    print("-" * 80)
    
    total_tests = 0
    total_errors = 0
    total_failures = 0
    
    for name, result in results:
        num_tests = result.testsRun
        num_errors = len(result.errors)
        num_failures = len(result.failures)
        total_tests += num_tests
        total_errors += num_errors
        total_failures += num_failures
        
        status = "✅ PASSED" if num_errors == 0 and num_failures == 0 else "❌ FAILED"
        print(f"{name:<25} {num_tests:>3} tests, {num_errors:>3} errors, {num_failures:>3} failures - {status}")
    
    print("-" * 80)
    overall_status = "✅ PASSED" if total_errors == 0 and total_failures == 0 else "❌ FAILED"
    print(f"TOTAL: {total_tests} tests, {total_errors} errors, {total_failures} failures - {overall_status}")
    print("=" * 80)
    
    return total_errors == 0 and total_failures == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 