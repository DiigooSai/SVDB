# SVDB Core Storage Engine

The SVDB Core Storage Engine is a high-performance file storage and hashing system built in Rust with Python bindings. It provides efficient content-addressed storage backed by RocksDB.

## Features

- **High-performance hashing** - Uses blake3 as the primary hash algorithm with Blake2b and Keccak256 fallbacks.
- **Content-addressed storage** - Files are identified and retrieved by their hash.
- **File chunking** - Large files can be broken into chunks for more efficient storage and retrieval.
- **Python integration** - Easy-to-use Python API with type annotations.
- **Command-line interface** - CLI for basic operations.
- **Fallback implementation** - Pure Python implementation when Rust compiler is unavailable.

## Installation

### From Source (Python Fallback Mode)

```bash
# Clone the repository
git clone https://github.com/yourusername/svdb.git
cd svdb/storage_engine

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

### Using Maturin (for full Rust implementation)

```bash
cd svdb/storage_engine
pip install maturin
maturin develop
```

## Testing

Run the included test script to verify functionality:

```bash
python3 test_svdb.py
```

This will run a series of tests to check:
- Hashing with different algorithms
- Storage and retrieval
- File chunking
- File integrity verification
- Path-based operations

## Usage

### Python API

```python
from svdb_core import store_file, retrieve_file, calculate_hash

# Store a file
db_path = "./data"
with open("my_file.txt", "rb") as f:
    data = f.read()
    
hash_val = store_file(db_path, data)
print(f"File stored with hash: {hash_val}")

# Retrieve a file
retrieved_data = retrieve_file(db_path, hash_val)

# Calculate a hash
file_hash = calculate_hash(data)
```

### Advanced Usage

```python
from svdb_core import (
    store_file_with_options, 
    HASH_ALGORITHM_BLAKE3,
    HASH_ALGORITHM_BLAKE2B,
    HASH_ALGORITHM_KECCAK256,
)

# Store with different hash algorithm
hash_val = store_file_with_options(
    db_path, 
    data, 
    algorithm=HASH_ALGORITHM_BLAKE2B,
    chunk_size=1024*1024  # 1MB chunks
)
```

### Helper Functions

```python
from svdb_core.helpers import store_file_from_path, retrieve_file_to_path

# Store a file from a path
hash_val = store_file_from_path(db_path, "my_file.txt")

# Retrieve a file to a path
retrieve_file_to_path(db_path, hash_val, "retrieved_file.txt")
```

### Command-Line Interface

```bash
# Calculate a file hash
svdb-core hash sample.txt

# Store a file
svdb-core store sample.txt --db ./data

# Retrieve a file by hash
svdb-core retrieve abc123def456... --db ./data --output retrieved.txt

# Verify a file's integrity
svdb-core verify abc123def456... --db ./data

# Batch store multiple files
svdb-core batch file1.txt file2.txt --db ./data
```

## Implementation Details

The storage engine uses RocksDB as its underlying key-value store and implements the following:

- **Hashing**: Files are hashed using blake3 by default, with optional Blake2b and Keccak256 algorithms.
- **Storage**: Files are stored directly or chunked based on size.
- **Caching**: Recently accessed files are cached for faster retrieval.
- **Verification**: File integrity can be verified by recomputing and comparing hashes.
- **Fallback Mode**: A pure Python implementation is available when the Rust compiler is not available or when RocksDB dependencies cannot be satisfied.

## Current Status

- ✅ Phase 1 Complete: Core Storage Engine
  - Implemented file hashing with multiple algorithms
  - Implemented file chunking for large files
  - Added Python bindings and CLI
  - Created fallback Python implementation

## License

MIT 