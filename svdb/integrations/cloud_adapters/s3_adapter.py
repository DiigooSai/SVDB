"""
AWS S3 Storage Adapter for SVDB
"""
import io
import os
import json
import logging
import tempfile
from typing import List, Dict, Any, BinaryIO, Optional, Tuple

from . import CloudStorageAdapter

logger = logging.getLogger("svdb.integrations.s3")

class S3Adapter(CloudStorageAdapter):
    """AWS S3 Storage Adapter"""
    
    def __init__(
        self, 
        bucket_name: str, 
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: Optional[str] = None
    ):
        """
        Initialize S3 adapter with credentials
        
        Args:
            bucket_name: S3 bucket name
            aws_access_key_id: AWS access key ID (optional, can use environment variables)
            aws_secret_access_key: AWS secret access key (optional, can use environment variables)
            region_name: AWS region name (optional, defaults to us-east-1)
        """
        self.bucket_name = bucket_name
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name or 'us-east-1'
        self.s3_client = None
        
        # For storing import results to avoid duplicate imports
        self.import_cache = {}
    
    def connect(self) -> bool:
        """Connect to AWS S3"""
        try:
            import boto3
            
            # Create S3 client
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.region_name
            )
            
            # Verify connection by checking if bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        
        except ImportError:
            logger.error("boto3 package is required for S3 adapter")
            return False
        
        except Exception as e:
            logger.error(f"Failed to connect to S3: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """List files in the S3 bucket with optional prefix"""
        if not self.s3_client:
            if not self.connect():
                logger.error("Cannot list files: not connected to S3")
                return []
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            files = []
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        files.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'etag': obj['ETag'].strip('"')
                        })
            
            return files
        
        except Exception as e:
            logger.error(f"Failed to list files in S3: {e}")
            return []
    
    def get_file(self, file_key: str) -> BinaryIO:
        """Get a file from S3 as a file-like object"""
        if not self.s3_client:
            if not self.connect():
                raise ConnectionError("Cannot get file: not connected to S3")
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
            file_content = response['Body'].read()
            return io.BytesIO(file_content)
        
        except Exception as e:
            logger.error(f"Failed to get file from S3: {e}")
            raise
    
    def get_file_metadata(self, file_key: str) -> Dict[str, Any]:
        """Get metadata for a file in S3"""
        if not self.s3_client:
            if not self.connect():
                raise ConnectionError("Cannot get metadata: not connected to S3")
        
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=file_key)
            
            metadata = {
                'key': file_key,
                'size': response['ContentLength'],
                'last_modified': response['LastModified'],
                'etag': response['ETag'].strip('"'),
                'content_type': response.get('ContentType', 'application/octet-stream')
            }
            
            # Add user metadata if present
            if 'Metadata' in response:
                metadata['user_metadata'] = response['Metadata']
            
            return metadata
        
        except Exception as e:
            logger.error(f"Failed to get file metadata from S3: {e}")
            raise
    
    def import_file(self, file_key: str, svdb_path: str) -> Tuple[str, Optional[str]]:
        """Import a file from S3 to SVDB"""
        # Check cache first
        cache_key = f"{file_key}:{svdb_path}"
        if cache_key in self.import_cache:
            return self.import_cache[cache_key]
        
        if not self.s3_client:
            if not self.connect():
                raise ConnectionError("Cannot import file: not connected to S3")
        
        try:
            # Import required here to avoid circular import
            import sys
            from pathlib import Path
            
            # Add parent directory to path
            parent_dir = str(Path(__file__).resolve().parent.parent.parent)
            if parent_dir not in sys.path:
                sys.path.append(parent_dir)
            
            # Import SVDB components
            from svdb_core import store_file_with_options
            from blockchain_bridge.bridge import BlockchainBridge
            
            # Get file content
            file_content = self.get_file(file_key).read()
            
            # Get file metadata
            metadata = self.get_file_metadata(file_key)
            
            # Store file in SVDB
            file_hash = store_file_with_options(svdb_path, file_content)
            
            # Prepare metadata for blockchain
            blockchain_metadata = {
                'source': 's3',
                'bucket': self.bucket_name,
                'key': file_key,
                'size': metadata['size'],
                'etag': metadata['etag'],
                'content_type': metadata.get('content_type', 'application/octet-stream'),
                'import_timestamp': int(os.path.time())
            }
            
            # Submit to blockchain
            try:
                async def submit_to_blockchain():
                    async with BlockchainBridge() as bridge:
                        return await bridge.submit_transaction(file_hash, blockchain_metadata)
                
                import asyncio
                tx_hash = asyncio.run(submit_to_blockchain())
            except Exception as e:
                logger.error(f"Failed to submit to blockchain: {e}")
                tx_hash = None
            
            # Cache the result
            result = (file_hash, tx_hash)
            self.import_cache[cache_key] = result
            return result
        
        except Exception as e:
            logger.error(f"Failed to import file from S3: {e}")
            raise
    
    def import_files(self, file_keys: List[str], svdb_path: str) -> Dict[str, Tuple[str, Optional[str]]]:
        """Import multiple files from S3 to SVDB"""
        results = {}
        
        for file_key in file_keys:
            try:
                file_hash, tx_hash = self.import_file(file_key, svdb_path)
                results[file_key] = (file_hash, tx_hash)
            except Exception as e:
                logger.error(f"Failed to import file {file_key}: {e}")
                results[file_key] = (None, None)
        
        return results


# Convenience function to create adapter from environment variables
def create_s3_adapter_from_env() -> S3Adapter:
    """
    Create S3 adapter from environment variables
    
    Required environment variables:
    - AWS_S3_BUCKET: S3 bucket name
    
    Optional environment variables:
    - AWS_ACCESS_KEY_ID: AWS access key ID
    - AWS_SECRET_ACCESS_KEY: AWS secret access key
    - AWS_REGION: AWS region name
    
    Returns:
        Configured S3Adapter instance
    """
    bucket_name = os.getenv('AWS_S3_BUCKET')
    if not bucket_name:
        raise ValueError("AWS_S3_BUCKET environment variable is required")
    
    return S3Adapter(
        bucket_name=bucket_name,
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION')
    ) 