import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, BinaryIO

from . import (
    store_file, 
    retrieve_file, 
    calculate_hash, 
    store_file_with_options,
    calculate_hash_with_algorithm,
    HASH_ALGORITHM_BLAKE3,
    HASH_ALGORITHM_BLAKE2B,
    HASH_ALGORITHM_KECCAK256,
    DEFAULT_CHUNK_SIZE,
)


def store_file_from_path(db_path: str, file_path: str, 
                         algorithm: str = HASH_ALGORITHM_BLAKE3,
                         chunk_size: int = 0) -> str:
    """
    Store a file from a path.
    
    Args:
        db_path: Path to the database directory
        file_path: Path to the file to store
        algorithm: Hash algorithm to use
        chunk_size: Size of chunks in bytes (0 for no chunking)
        
    Returns:
        The hash of the stored file
    """
    with open(file_path, 'rb') as f:
        data = f.read()
    
    return store_file_with_options(db_path, data, algorithm, chunk_size)


def retrieve_file_to_path(db_path: str, hash_val: str, output_path: str) -> None:
    """
    Retrieve a file and save it to a path.
    
    Args:
        db_path: Path to the database directory
        hash_val: Hash of the file to retrieve
        output_path: Path to save the file to
    """
    data = retrieve_file(db_path, hash_val)
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    with open(output_path, 'wb') as f:
        f.write(data)


def batch_store_files(db_path: str, 
                     file_paths: List[str], 
                     algorithm: str = HASH_ALGORITHM_BLAKE3,
                     chunk_size: int = 0) -> Dict[str, str]:
    """
    Store multiple files and return their hashes.
    
    Args:
        db_path: Path to the database directory
        file_paths: List of paths to files to store
        algorithm: Hash algorithm to use
        chunk_size: Size of chunks in bytes (0 for no chunking)
        
    Returns:
        Dictionary mapping file paths to their hashes
    """
    results = {}
    for file_path in file_paths:
        try:
            hash_val = store_file_from_path(db_path, file_path, algorithm, chunk_size)
            results[file_path] = hash_val
        except Exception as e:
            results[file_path] = f"Error: {str(e)}"
    
    return results


def verify_file_integrity(db_path: str, hash_val: str, algorithm: str = HASH_ALGORITHM_BLAKE3) -> bool:
    """
    Verify the integrity of a stored file by retrieving it and checking its hash.
    
    Args:
        db_path: Path to the database directory
        hash_val: Hash of the file to verify
        algorithm: Hash algorithm to use
        
    Returns:
        True if the file is intact, False otherwise
    """
    try:
        data = retrieve_file(db_path, hash_val)
        computed_hash = calculate_hash_with_algorithm(data, algorithm)
        return computed_hash == hash_val
    except Exception:
        return False


def get_all_hashes(db_path: str) -> List[str]:
    """
    Get a list of all file hashes in the database.
    
    Args:
        db_path: Path to the database directory
        
    Returns:
        List of file hashes
    """
    # This is a simplistic implementation that works based on our knowledge of RocksDB structure
    # In a real implementation, you would use RocksDB's iterator functionality
    
    # Look for .sst files in the DB directory
    db_dir = Path(db_path)
    if not db_dir.exists():
        return []
    
    # We'll use a metadata directory to store hash listings
    meta_dir = db_dir / "metadata"
    if not meta_dir.exists():
        return []
    
    hash_file = meta_dir / "hashes.json"
    if not hash_file.exists():
        return []
    
    try:
        with open(hash_file, 'r') as f:
            return json.load(f)
    except Exception:
        return []


def update_hash_listing(db_path: str, hash_val: str, add: bool = True) -> None:
    """
    Update the hash listing in the metadata directory.
    
    Args:
        db_path: Path to the database directory
        hash_val: Hash to add or remove
        add: True to add, False to remove
    """
    db_dir = Path(db_path)
    meta_dir = db_dir / "metadata"
    meta_dir.mkdir(exist_ok=True)
    
    hash_file = meta_dir / "hashes.json"
    
    hashes = []
    if hash_file.exists():
        try:
            with open(hash_file, 'r') as f:
                hashes = json.load(f)
        except Exception:
            pass
    
    if add and hash_val not in hashes:
        hashes.append(hash_val)
    elif not add and hash_val in hashes:
        hashes.remove(hash_val)
    
    with open(hash_file, 'w') as f:
        json.dump(hashes, f)


def stream_store_file(db_path: str, file_stream: BinaryIO, 
                     algorithm: str = HASH_ALGORITHM_BLAKE3,
                     chunk_size: int = DEFAULT_CHUNK_SIZE) -> str:
    """
    Store a file from a file-like object using streaming to handle large files.
    
    Args:
        db_path: Path to the database directory
        file_stream: File-like object to read from
        algorithm: Hash algorithm to use
        chunk_size: Size of chunks in bytes
        
    Returns:
        The hash of the stored file
    """
    # For small files, just read the whole thing
    data = file_stream.read(chunk_size)
    if len(data) < chunk_size:
        return store_file_with_options(db_path, data, algorithm, 0)
    
    # For large files, we'll use chunking
    chunks = [data]
    while True:
        chunk = file_stream.read(chunk_size)
        if not chunk:
            break
        chunks.append(chunk)
    
    # Combine chunks into one buffer and store
    all_data = b''.join(chunks)
    return store_file_with_options(db_path, all_data, algorithm, chunk_size)


def list_files_by_hash_prefix(db_path: str, prefix: str) -> List[str]:
    """
    List files with hashes that start with the given prefix.
    
    Args:
        db_path: Path to the database directory
        prefix: Hash prefix to match
        
    Returns:
        List of matching hashes
    """
    all_hashes = get_all_hashes(db_path)
    return [h for h in all_hashes if h.startswith(prefix)]


def calculate_file_hash(file_path: str, algorithm: str = HASH_ALGORITHM_BLAKE3) -> str:
    """
    Calculate the hash of a file without storing it.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use
        
    Returns:
        The hash of the file
    """
    with open(file_path, 'rb') as f:
        data = f.read()
    
    return calculate_hash_with_algorithm(data, algorithm) 