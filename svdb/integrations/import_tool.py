#!/usr/bin/env python3
"""
SVDB Import Tool
Command-line utility for importing data from Web2 storage providers to SVDB.
"""
import os
import sys
import json
import argparse
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add parent directory to path for imports
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("svdb.import_tool")

# Import cloud adapters
try:
    from .cloud_adapters import (
        CloudStorageAdapter,
        S3Adapter,
        AzureBlobAdapter,
        GCPStorageAdapter,
        DOSpacesAdapter,
    )
except ImportError:
    try:
        # Alternative import path
        from cloud_adapters import (
            CloudStorageAdapter,
            S3Adapter,
            AzureBlobAdapter,
            GCPStorageAdapter,
            DOSpacesAdapter,
        )
    except ImportError:
        logger.error("Cloud adapters not found. Make sure the module is correctly installed.")
        sys.exit(1)

# Factory function to create the appropriate adapter
def create_adapter(provider: str, config: Dict[str, Any]) -> CloudStorageAdapter:
    """
    Create a cloud storage adapter based on provider name
    
    Args:
        provider: Cloud provider name (s3, azure, gcp, do)
        config: Configuration for the adapter
        
    Returns:
        Configured CloudStorageAdapter
    """
    if provider == 's3':
        return S3Adapter(
            bucket_name=config['bucket'],
            aws_access_key_id=config.get('access_key_id'),
            aws_secret_access_key=config.get('secret_access_key'),
            region_name=config.get('region')
        )
    elif provider == 'azure':
        return AzureBlobAdapter(
            account_name=config['account_name'],
            container_name=config['container'],
            account_key=config.get('account_key'),
            connection_string=config.get('connection_string')
        )
    elif provider == 'gcp':
        return GCPStorageAdapter(
            bucket_name=config['bucket'],
            credentials_file=config.get('credentials_file')
        )
    elif provider == 'do':
        return DOSpacesAdapter(
            space_name=config['space'],
            region=config['region'],
            access_key=config.get('access_key'),
            secret_key=config.get('secret_key')
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")

def load_config(config_file: str) -> Dict[str, Any]:
    """
    Load configuration from a JSON file
    
    Args:
        config_file: Path to the configuration file
        
    Returns:
        Configuration dictionary
    """
    with open(config_file, 'r') as f:
        return json.load(f)

def save_results(results: Dict[str, Tuple[str, Optional[str]]], output_file: str):
    """
    Save import results to a JSON file
    
    Args:
        results: Dictionary mapping file keys to (file_hash, tx_hash) tuples
        output_file: Path to save results to
    """
    # Convert results to serializable format
    serializable_results = {}
    for file_key, (file_hash, tx_hash) in results.items():
        serializable_results[file_key] = {
            'file_hash': file_hash,
            'tx_hash': tx_hash
        }
    
    with open(output_file, 'w') as f:
        json.dump(serializable_results, f, indent=2)
    
    logger.info(f"Results saved to {output_file}")

async def import_single_file(
    adapter: CloudStorageAdapter,
    file_key: str, 
    svdb_path: str
) -> Tuple[str, Optional[str]]:
    """
    Import a single file and wait for blockchain confirmation
    
    Args:
        adapter: Cloud storage adapter
        file_key: Key/path of the file to import
        svdb_path: Path to SVDB database
        
    Returns:
        Tuple of (file_hash, tx_hash)
    """
    # Import blockchain components
    from blockchain_bridge.bridge import BlockchainBridge
    
    # Import file
    file_hash, tx_hash = adapter.import_file(file_key, svdb_path)
    
    if tx_hash:
        # Check transaction status
        async with BlockchainBridge() as bridge:
            status = await bridge.check_confirmation_status(tx_hash)
            logger.info(f"Transaction status for {file_key}: {status.get('status', 'unknown')}")
    
    return file_hash, tx_hash

async def run_import(args: argparse.Namespace):
    """
    Run the import process based on command-line arguments
    
    Args:
        args: Command-line arguments
    """
    # Load configuration
    if args.config:
        config = load_config(args.config)
    else:
        # Use environment variables for configuration
        provider = args.provider.lower()
        if provider == 's3':
            config = {
                'bucket': os.getenv('AWS_S3_BUCKET'),
                'access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
                'secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
                'region': os.getenv('AWS_REGION')
            }
        elif provider == 'azure':
            config = {
                'account_name': os.getenv('AZURE_STORAGE_ACCOUNT'),
                'container': os.getenv('AZURE_STORAGE_CONTAINER'),
                'account_key': os.getenv('AZURE_STORAGE_KEY'),
                'connection_string': os.getenv('AZURE_STORAGE_CONNECTION_STRING')
            }
        elif provider == 'gcp':
            config = {
                'bucket': os.getenv('GCP_STORAGE_BUCKET'),
                'credentials_file': os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            }
        elif provider == 'do':
            config = {
                'space': os.getenv('DO_SPACES_NAME'),
                'region': os.getenv('DO_SPACES_REGION'),
                'access_key': os.getenv('DO_SPACES_KEY'),
                'secret_key': os.getenv('DO_SPACES_SECRET')
            }
        else:
            logger.error(f"Unsupported provider: {provider}")
            return
    
    # Create adapter
    try:
        adapter = create_adapter(args.provider.lower(), config)
    except ValueError as e:
        logger.error(str(e))
        return
    except Exception as e:
        logger.error(f"Failed to create adapter: {e}")
        return
    
    # Connect to cloud provider
    if not adapter.connect():
        logger.error(f"Failed to connect to {args.provider}")
        return
    
    # Get files to import
    files_to_import = []
    
    if args.file:
        # Import specific file
        files_to_import = [args.file]
    elif args.prefix:
        # List files with prefix
        file_list = adapter.list_files(args.prefix)
        files_to_import = [file['key'] for file in file_list]
        logger.info(f"Found {len(files_to_import)} files with prefix '{args.prefix}'")
    elif args.file_list:
        # Load file list from file
        with open(args.file_list, 'r') as f:
            files_to_import = [line.strip() for line in f if line.strip()]
    else:
        logger.error("No files specified to import")
        return
    
    # Filter files if needed
    if args.limit and len(files_to_import) > args.limit:
        logger.info(f"Limiting import to {args.limit} files")
        files_to_import = files_to_import[:args.limit]
    
    # Set up SVDB path
    svdb_path = args.db_path or os.getenv("SVDB_DB_PATH", "./data")
    
    # Import files
    if args.parallel:
        # Import files in parallel
        results = adapter.import_files(files_to_import, svdb_path)
    else:
        # Import files sequentially with updates
        results = {}
        for i, file_key in enumerate(files_to_import):
            try:
                logger.info(f"Importing file {i+1}/{len(files_to_import)}: {file_key}")
                file_hash, tx_hash = await import_single_file(adapter, file_key, svdb_path)
                results[file_key] = (file_hash, tx_hash)
                logger.info(f"Imported {file_key} -> {file_hash} (tx: {tx_hash or 'pending'})")
            except Exception as e:
                logger.error(f"Failed to import {file_key}: {e}")
                results[file_key] = (None, None)
    
    # Save results
    if args.output:
        save_results(results, args.output)
    
    # Print summary
    success_count = sum(1 for _, (file_hash, _) in results.items() if file_hash)
    logger.info(f"Import complete: {success_count}/{len(files_to_import)} files imported successfully")


def main():
    """Main entry point for the import tool"""
    parser = argparse.ArgumentParser(description="Import data from Web2 storage to SVDB")
    
    # Provider selection
    parser.add_argument(
        "provider",
        choices=["s3", "azure", "gcp", "do"],
        help="Cloud storage provider"
    )
    
    # File selection (mutually exclusive)
    file_group = parser.add_mutually_exclusive_group(required=True)
    file_group.add_argument(
        "--file",
        help="Specific file to import"
    )
    file_group.add_argument(
        "--prefix",
        help="Prefix for files to import"
    )
    file_group.add_argument(
        "--file-list",
        help="File containing list of files to import (one per line)"
    )
    
    # Configuration
    parser.add_argument(
        "--config",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--db-path",
        help="Path to SVDB database (default: value from SVDB_DB_PATH env var or ./data)"
    )
    
    # Import options
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of files to import"
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Import files in parallel"
    )
    parser.add_argument(
        "--output",
        help="Path to save import results"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Run import
    asyncio.run(run_import(args))


if __name__ == "__main__":
    main() 