#!/usr/bin/env python3
"""
Simple command-line tool for SVDB core operations
"""
import os
import sys
import argparse
from . import (
    calculate_hash,
    calculate_hash_with_algorithm,
    store_file,
    store_file_with_options,
    retrieve_file,
    HASH_ALGORITHM_BLAKE3,
    HASH_ALGORITHM_BLAKE2B,
    HASH_ALGORITHM_KECCAK256,
    DEFAULT_CHUNK_SIZE,
)
from .helpers import (
    store_file_from_path,
    retrieve_file_to_path,
    batch_store_files,
    verify_file_integrity,
    calculate_file_hash
)

def main():
    parser = argparse.ArgumentParser(description="SVDB Core Storage Engine CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Hash command
    hash_parser = subparsers.add_parser("hash", help="Calculate hash of a file")
    hash_parser.add_argument("file", help="Path to file")
    hash_parser.add_argument("--algorithm", "-a", 
                          choices=[HASH_ALGORITHM_BLAKE3, HASH_ALGORITHM_BLAKE2B, HASH_ALGORITHM_KECCAK256],
                          default=HASH_ALGORITHM_BLAKE3,
                          help="Hash algorithm to use")
    
    # Store command
    store_parser = subparsers.add_parser("store", help="Store a file")
    store_parser.add_argument("file", help="Path to file")
    store_parser.add_argument("--db", required=True, help="Path to database directory")
    store_parser.add_argument("--algorithm", "-a", 
                           choices=[HASH_ALGORITHM_BLAKE3, HASH_ALGORITHM_BLAKE2B, HASH_ALGORITHM_KECCAK256],
                           default=HASH_ALGORITHM_BLAKE3,
                           help="Hash algorithm to use")
    store_parser.add_argument("--chunk-size", "-c", type=int, default=0,
                          help="Chunk size in bytes (0 for no chunking)")
    
    # Retrieve command
    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve a file")
    retrieve_parser.add_argument("hash", help="Hash of the file")
    retrieve_parser.add_argument("--db", required=True, help="Path to database directory")
    retrieve_parser.add_argument("--output", "-o", required=True, help="Output file path")
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify file integrity")
    verify_parser.add_argument("hash", help="Hash of the file")
    verify_parser.add_argument("--db", required=True, help="Path to database directory")
    
    # Batch store command
    batch_parser = subparsers.add_parser("batch", help="Batch store files")
    batch_parser.add_argument("files", nargs="+", help="Paths to files")
    batch_parser.add_argument("--db", required=True, help="Path to database directory")
    batch_parser.add_argument("--algorithm", "-a", 
                          choices=[HASH_ALGORITHM_BLAKE3, HASH_ALGORITHM_BLAKE2B, HASH_ALGORITHM_KECCAK256],
                          default=HASH_ALGORITHM_BLAKE3,
                          help="Hash algorithm to use")
    
    args = parser.parse_args()
    
    # Process commands
    if args.command == "hash":
        hash_val = calculate_file_hash(args.file, args.algorithm)
        print(f"Hash ({args.algorithm}): {hash_val}")
    
    elif args.command == "store":
        hash_val = store_file_from_path(args.db, args.file, args.algorithm, args.chunk_size)
        print(f"Stored file with hash: {hash_val}")
    
    elif args.command == "retrieve":
        retrieve_file_to_path(args.db, args.hash, args.output)
        print(f"Retrieved file to: {args.output}")
    
    elif args.command == "verify":
        result = verify_file_integrity(args.db, args.hash)
        if result:
            print(f"File integrity verified: {args.hash}")
        else:
            print(f"File integrity verification failed: {args.hash}")
            sys.exit(1)
    
    elif args.command == "batch":
        results = batch_store_files(args.db, args.files, args.algorithm)
        for file_path, result in results.items():
            if result.startswith("Error:"):
                print(f"Failed to store {file_path}: {result}")
            else:
                print(f"Stored {file_path} with hash: {result}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 