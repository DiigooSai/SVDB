from typing import Optional
import os
import hashlib
from pathlib import Path
try:
    import blake3 as blake3module  # Pure Python implementation as fallback
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False

try:
    from . import _svdb_core
    HAS_RUST_CORE = True
except ImportError:
    HAS_RUST_CORE = False
    # Mock implementation for development without Rust module
    class MockSvdbCore:
        @staticmethod
        def py_calculate_hash(data):
            # Try native blake3 first if available
            if HAS_BLAKE3:
                return blake3module.blake3(data).hexdigest()
            # Fall back to blake2b which is available in hashlib
            return hashlib.blake2b(data).hexdigest()
        
        @staticmethod
        def py_calculate_hash_with_algorithm(data, algorithm):
            if algorithm == "blake3":
                if HAS_BLAKE3:
                    return blake3module.blake3(data).hexdigest()
                # Fall back to blake2b if blake3 not available
                return hashlib.blake2b(data).hexdigest()
            elif algorithm == "blake2b":
                return hashlib.blake2b(data).hexdigest()
            elif algorithm == "keccak256":
                try:
                    # Try to use cryptography's Keccak
                    from cryptography.hazmat.primitives import hashes
                    digest = hashes.Hash(hashes.SHA3_256())
                    digest.update(data)
                    return digest.finalize().hex()
                except ImportError:
                    # Fall back to sha3_256 as last resort
                    return hashlib.sha3_256(data).hexdigest()
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        @staticmethod
        def py_store_file(db_path, data):
            hash_val = MockSvdbCore.py_calculate_hash(data)
            # Mock storage
            os.makedirs(os.path.join(db_path, 'data'), exist_ok=True)
            with open(os.path.join(db_path, 'data', hash_val), 'wb') as f:
                f.write(data)
            return hash_val
        
        @staticmethod
        def py_store_file_with_options(db_path, data, algorithm, chunk_size):
            hash_val = MockSvdbCore.py_calculate_hash_with_algorithm(data, algorithm)
            
            # Create database directory structure
            data_dir = os.path.join(db_path, 'data')
            os.makedirs(data_dir, exist_ok=True)
            
            # Implement basic chunking
            if chunk_size > 0 and len(data) > chunk_size:
                # Create metadata directory
                meta_dir = os.path.join(db_path, 'metadata')
                os.makedirs(meta_dir, exist_ok=True)
                
                # Calculate chunk hashes and store chunks
                chunks = []
                chunk_hashes = []
                
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i+chunk_size]
                    chunk_hash = MockSvdbCore.py_calculate_hash_with_algorithm(chunk, algorithm)
                    chunk_hashes.append(chunk_hash)
                    chunks.append(chunk)
                    
                    # Store chunk
                    chunk_path = os.path.join(data_dir, f"chunk_{hash_val}_{i//chunk_size}")
                    with open(chunk_path, 'wb') as f:
                        f.write(chunk)
                
                # Store metadata
                metadata = {
                    "hash": hash_val,
                    "algorithm": algorithm,
                    "size": len(data),
                    "chunk_size": chunk_size,
                    "chunks": chunk_hashes,
                }
                
                import json
                meta_path = os.path.join(meta_dir, f"meta_{hash_val}")
                with open(meta_path, 'w') as f:
                    json.dump(metadata, f)
            else:
                # Store as a single file
                with open(os.path.join(data_dir, hash_val), 'wb') as f:
                    f.write(data)
            
            return hash_val
        
        @staticmethod
        def py_retrieve_file(db_path, hash_val):
            # Check if it's a chunked file
            meta_path = os.path.join(db_path, 'metadata', f"meta_{hash_val}")
            if os.path.exists(meta_path):
                # Reassemble chunked file
                import json
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
                
                # Get all chunks
                data = bytearray()
                for i in range(len(metadata["chunks"])):
                    chunk_path = os.path.join(db_path, 'data', f"chunk_{hash_val}_{i}")
                    with open(chunk_path, 'rb') as f:
                        data.extend(f.read())
                
                return bytes(data)
            else:
                # Regular file
                file_path = os.path.join(db_path, 'data', hash_val)
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"File with hash {hash_val} not found")
                with open(file_path, 'rb') as f:
                    return f.read()
    
    _svdb_core = MockSvdbCore()


def calculate_hash(data: bytes) -> str:
    """
    Calculate the hash of data using the default algorithm (blake3).
    
    Args:
        data: Bytes to hash
        
    Returns:
        The hex-encoded hash
    """
    return _svdb_core.py_calculate_hash(data)


def calculate_hash_with_algorithm(data: bytes, algorithm: str) -> str:
    """
    Calculate the hash of data using the specified algorithm.
    
    Args:
        data: Bytes to hash
        algorithm: Hash algorithm to use ('blake3', 'blake2b', or 'keccak256')
        
    Returns:
        The hex-encoded hash
    """
    return _svdb_core.py_calculate_hash_with_algorithm(data, algorithm)


def store_file(db_path: str, data: bytes) -> str:
    """
    Store a file using the default settings (blake3, no chunking).
    
    Args:
        db_path: Path to the database directory
        data: File data to store
        
    Returns:
        The hash of the stored file
    """
    return _svdb_core.py_store_file(db_path, data)


def store_file_with_options(db_path: str, data: bytes, algorithm: str = 'blake3', chunk_size: int = 0) -> str:
    """
    Store a file with the specified options.
    
    Args:
        db_path: Path to the database directory
        data: File data to store
        algorithm: Hash algorithm to use ('blake3', 'blake2b', or 'keccak256')
        chunk_size: Size of chunks in bytes (0 for no chunking)
        
    Returns:
        The hash of the stored file
    """
    return _svdb_core.py_store_file_with_options(db_path, data, algorithm, chunk_size)


def retrieve_file(db_path: str, hash_val: str) -> bytes:
    """
    Retrieve a file by its hash.
    
    Args:
        db_path: Path to the database directory
        hash_val: Hash of the file to retrieve
        
    Returns:
        The file data
    """
    return _svdb_core.py_retrieve_file(db_path, hash_val)


# Convenient hash algorithm constants
HASH_ALGORITHM_BLAKE3 = 'blake3'
HASH_ALGORITHM_BLAKE2B = 'blake2b'
HASH_ALGORITHM_KECCAK256 = 'keccak256'

# Default chunk size (1MB)
DEFAULT_CHUNK_SIZE = 1024 * 1024


# Log implementation details
if HAS_RUST_CORE:
    print("SVDB Core: Using native Rust implementation")
else:
    print("SVDB Core: Using Python fallback implementation")
    if HAS_BLAKE3:
        print("  - Using native Blake3 hashing")
    else:
        print("  - Using Blake2b as fallback for Blake3") 