"""
SVDB Cloud Storage Adapters
Provides integration with various cloud storage providers.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, BinaryIO, Optional, Tuple

class CloudStorageAdapter(ABC):
    """Base abstract class for all cloud storage adapters"""
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the cloud provider
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def list_files(self, prefix: str = "") -> List[Dict[str, Any]]:
        """
        List files in the storage, optionally filtered by prefix
        
        Args:
            prefix: Optional prefix to filter files by
            
        Returns:
            List of file metadata dictionaries
        """
        pass
    
    @abstractmethod
    def get_file(self, file_key: str) -> BinaryIO:
        """
        Get a file's content as a file-like object
        
        Args:
            file_key: The key/path of the file to retrieve
            
        Returns:
            File-like object with the file's content
        """
        pass
        
    @abstractmethod
    def get_file_metadata(self, file_key: str) -> Dict[str, Any]:
        """
        Get metadata for a specific file
        
        Args:
            file_key: The key/path of the file to get metadata for
            
        Returns:
            Dictionary with file metadata
        """
        pass
    
    @abstractmethod
    def import_file(self, file_key: str, svdb_path: str) -> Tuple[str, Optional[str]]:
        """
        Import a file from cloud storage to SVDB
        
        Args:
            file_key: The key/path of the file in cloud storage
            svdb_path: Path to the SVDB database
            
        Returns:
            Tuple of (file_hash, tx_hash)
        """
        pass
    
    @abstractmethod
    def import_files(self, file_keys: List[str], svdb_path: str) -> Dict[str, Tuple[str, Optional[str]]]:
        """
        Import multiple files from cloud storage to SVDB
        
        Args:
            file_keys: List of file keys to import
            svdb_path: Path to the SVDB database
            
        Returns:
            Dictionary mapping file keys to (file_hash, tx_hash) tuples
        """
        pass

# Import specific adapters
from .s3_adapter import S3Adapter
from .azure_adapter import AzureBlobAdapter
from .gcp_adapter import GCPStorageAdapter
from .do_adapter import DOSpacesAdapter

__all__ = [
    'CloudStorageAdapter',
    'S3Adapter',
    'AzureBlobAdapter',
    'GCPStorageAdapter',
    'DOSpacesAdapter',
] 