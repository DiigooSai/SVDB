#!/usr/bin/env python3
"""
SVDB Hardware Security Module (HSM) Integration
This module handles secure key management and transaction signing using HSMs.
"""

import os
import json
import logging
import base64
from typing import Dict, Any, Optional, Tuple, Union
from enum import Enum
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("hsm_integration")

# Load environment variables
load_dotenv()

# HSM Configuration
HSM_ENABLED = os.getenv("USE_HSM", "false").lower() == "true"
HSM_PROVIDER = os.getenv("HSM_PROVIDER", "aws").lower()
HSM_CONFIG_PATH = os.getenv("HSM_CONFIG_PATH", "")


class HSMProvider(Enum):
    """Supported HSM providers"""
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    THALES = "thales"
    LOCAL = "local"  # Fallback for development only


class HSMError(Exception):
    """Base class for HSM-related errors"""
    pass


class HSMConfigError(HSMError):
    """Error in HSM configuration"""
    pass


class HSMConnectionError(HSMError):
    """Error connecting to the HSM service"""
    pass


class HSMSigningError(HSMError):
    """Error during signing operation"""
    pass


class HSM:
    """
    Hardware Security Module interface for secure key management and signing.
    
    This class provides a unified interface for different HSM providers,
    abstracting away the provider-specific implementation details.
    """
    
    def __init__(self, provider: Optional[str] = None, config_path: Optional[str] = None):
        """
        Initialize the HSM interface.
        
        Args:
            provider: HSM provider name (aws, azure, gcp, thales)
            config_path: Path to HSM configuration file
        """
        self.provider_name = provider or HSM_PROVIDER
        self.config_path = config_path or HSM_CONFIG_PATH
        self.client = None
        self.config = {}
        
        try:
            self.provider = HSMProvider(self.provider_name)
        except ValueError:
            logger.error(f"Unsupported HSM provider: {self.provider_name}")
            raise HSMConfigError(f"Unsupported HSM provider: {self.provider_name}")
        
        # Load configuration
        self._load_config()
        
        # Initialize the provider-specific client
        self._init_client()
        
        logger.info(f"HSM initialized with provider: {self.provider.value}")
    
    def _load_config(self) -> None:
        """Load HSM configuration from file"""
        if not self.config_path:
            logger.warning("No HSM config path provided, using environment variables")
            return
        
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            logger.info(f"Loaded HSM configuration from {self.config_path}")
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load HSM configuration: {e}")
            raise HSMConfigError(f"Failed to load HSM configuration: {e}")
    
    def _init_client(self) -> None:
        """Initialize the HSM client based on the provider"""
        try:
            if self.provider == HSMProvider.AWS:
                self._init_aws_client()
            elif self.provider == HSMProvider.AZURE:
                self._init_azure_client()
            elif self.provider == HSMProvider.GCP:
                self._init_gcp_client()
            elif self.provider == HSMProvider.THALES:
                self._init_thales_client()
            elif self.provider == HSMProvider.LOCAL:
                self._init_local_client()
            else:
                raise HSMConfigError(f"Unsupported HSM provider: {self.provider}")
        except Exception as e:
            logger.error(f"Failed to initialize HSM client: {e}")
            raise HSMConnectionError(f"Failed to initialize HSM client: {e}")
    
    def _init_aws_client(self) -> None:
        """Initialize AWS KMS client"""
        try:
            import boto3
            from botocore.config import Config
            
            # Get configuration
            region = self.config.get('region') or os.getenv('AWS_REGION', 'us-east-1')
            timeout = int(self.config.get('timeout') or os.getenv('AWS_TIMEOUT', '30'))
            
            # Configure AWS client
            aws_config = Config(
                region_name=region,
                connect_timeout=timeout,
                retries={'max_attempts': 3, 'mode': 'standard'}
            )
            
            # Create KMS client
            self.client = boto3.client('kms', config=aws_config)
            logger.info("AWS KMS client initialized")
        except ImportError:
            logger.error("boto3 package not installed. Run: pip install boto3")
            raise HSMConfigError("boto3 package not installed. Run: pip install boto3")
    
    def _init_azure_client(self) -> None:
        """Initialize Azure Key Vault client"""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.keys.crypto import CryptographyClient
            from azure.keyvault.keys import KeyClient
            
            # Get configuration
            vault_url = self.config.get('vault_url') or os.getenv('AZURE_VAULT_URL', '')
            key_name = self.config.get('key_name') or os.getenv('AZURE_KEY_NAME', '')
            
            if not vault_url or not key_name:
                raise HSMConfigError("Azure Key Vault URL and key name must be provided")
            
            # Create Azure clients
            credential = DefaultAzureCredential()
            key_client = KeyClient(vault_url=vault_url, credential=credential)
            key = key_client.get_key(key_name)
            
            # Create cryptography client for signing
            self.client = {
                'crypto_client': CryptographyClient(key, credential=credential),
                'key_name': key_name
            }
            logger.info("Azure Key Vault client initialized")
        except ImportError:
            logger.error("Azure packages not installed. Run: pip install azure-identity azure-keyvault-keys")
            raise HSMConfigError("Azure packages not installed. Run: pip install azure-identity azure-keyvault-keys")
    
    def _init_gcp_client(self) -> None:
        """Initialize Google Cloud KMS client"""
        try:
            from google.cloud import kms
            
            # Get configuration
            project_id = self.config.get('project_id') or os.getenv('GCP_PROJECT_ID', '')
            location = self.config.get('location') or os.getenv('GCP_LOCATION', 'global')
            key_ring = self.config.get('key_ring') or os.getenv('GCP_KEY_RING', '')
            key_name = self.config.get('key_name') or os.getenv('GCP_KEY_NAME', '')
            
            if not project_id or not key_ring or not key_name:
                raise HSMConfigError("GCP project ID, key ring, and key name must be provided")
            
            # Create GCP KMS client
            kms_client = kms.KeyManagementServiceClient()
            
            # Create the key name
            key_path = kms_client.crypto_key_path(project_id, location, key_ring, key_name)
            
            self.client = {
                'kms_client': kms_client,
                'key_path': key_path
            }
            logger.info("Google Cloud KMS client initialized")
        except ImportError:
            logger.error("Google Cloud KMS package not installed. Run: pip install google-cloud-kms")
            raise HSMConfigError("Google Cloud KMS package not installed. Run: pip install google-cloud-kms")
    
    def _init_thales_client(self) -> None:
        """Initialize Thales HSM client (placeholder for actual implementation)"""
        logger.warning("Thales HSM support is a placeholder. Implement according to your requirements.")
        raise NotImplementedError("Thales HSM integration not yet implemented")
    
    def _init_local_client(self) -> None:
        """Initialize local key management (for development only)"""
        logger.warning("Using local key management - NOT SECURE FOR PRODUCTION")
        
        # For development, we'll just use a simple in-memory "HSM"
        self.client = {
            'private_key': os.getenv('DEV_PRIVATE_KEY', '')
        }
        
        if not self.client['private_key']:
            logger.warning("No development private key set in DEV_PRIVATE_KEY environment variable")
    
    def sign_transaction(self, transaction_data: Union[str, bytes]) -> str:
        """
        Sign transaction data using the HSM.
        
        Args:
            transaction_data: The transaction data to sign
        
        Returns:
            The signature as a hex string
        """
        if isinstance(transaction_data, str):
            transaction_data = transaction_data.encode('utf-8')
        
        try:
            if not HSM_ENABLED:
                logger.warning("HSM is disabled, using alternative signing method")
                return self._fallback_sign(transaction_data)
            
            if self.provider == HSMProvider.AWS:
                return self._aws_sign(transaction_data)
            elif self.provider == HSMProvider.AZURE:
                return self._azure_sign(transaction_data)
            elif self.provider == HSMProvider.GCP:
                return self._gcp_sign(transaction_data)
            elif self.provider == HSMProvider.THALES:
                return self._thales_sign(transaction_data)
            elif self.provider == HSMProvider.LOCAL:
                return self._local_sign(transaction_data)
            else:
                raise HSMSigningError(f"Unsupported HSM provider: {self.provider}")
        except Exception as e:
            logger.error(f"Transaction signing failed: {e}")
            raise HSMSigningError(f"Transaction signing failed: {e}")
    
    def _aws_sign(self, transaction_data: bytes) -> str:
        """Sign using AWS KMS"""
        try:
            key_id = self.config.get('key_id') or os.getenv('AWS_KMS_KEY_ID', '')
            if not key_id:
                raise HSMSigningError("AWS KMS key ID not provided")
            
            # Sign the transaction
            response = self.client.sign(
                KeyId=key_id,
                Message=transaction_data,
                MessageType='RAW',
                SigningAlgorithm='ECDSA_SHA_256'
            )
            
            # Convert the binary signature to hex
            signature = response['Signature'].hex()
            logger.info(f"Transaction signed with AWS KMS, key ID: {key_id}")
            return signature
        except Exception as e:
            logger.error(f"AWS KMS signing failed: {e}")
            raise HSMSigningError(f"AWS KMS signing failed: {e}")
    
    def _azure_sign(self, transaction_data: bytes) -> str:
        """Sign using Azure Key Vault"""
        try:
            crypto_client = self.client['crypto_client']
            
            # Sign the transaction
            digest = self._compute_sha256(transaction_data)
            sign_result = crypto_client.sign("ES256", digest)
            
            # Convert the signature to hex
            signature = sign_result.signature.hex()
            logger.info(f"Transaction signed with Azure Key Vault, key: {self.client['key_name']}")
            return signature
        except Exception as e:
            logger.error(f"Azure Key Vault signing failed: {e}")
            raise HSMSigningError(f"Azure Key Vault signing failed: {e}")
    
    def _gcp_sign(self, transaction_data: bytes) -> str:
        """Sign using Google Cloud KMS"""
        try:
            kms_client = self.client['kms_client']
            key_path = self.client['key_path']
            
            # Create the digest
            digest = self._compute_sha256(transaction_data)
            
            # Sign the digest
            response = kms_client.asymmetric_sign(
                request={
                    "name": key_path,
                    "digest": {"sha256": digest},
                }
            )
            
            # Convert the signature to hex
            signature = response.signature.hex()
            logger.info(f"Transaction signed with Google Cloud KMS, key: {key_path}")
            return signature
        except Exception as e:
            logger.error(f"Google Cloud KMS signing failed: {e}")
            raise HSMSigningError(f"Google Cloud KMS signing failed: {e}")
    
    def _thales_sign(self, transaction_data: bytes) -> str:
        """Sign using Thales HSM (placeholder)"""
        raise NotImplementedError("Thales HSM signing not yet implemented")
    
    def _local_sign(self, transaction_data: bytes) -> str:
        """
        Sign using local key (development only).
        WARNING: This is not secure for production!
        """
        try:
            import ecdsa
            
            # Get the private key
            private_key_hex = self.client.get('private_key', '')
            if not private_key_hex:
                raise HSMSigningError("Development private key not set")
            
            # Convert hex private key to bytes
            private_key_bytes = bytes.fromhex(private_key_hex)
            
            # Create signing key
            sk = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
            
            # Sign the transaction
            signature = sk.sign(transaction_data)
            
            logger.warning("Transaction signed with LOCAL key - NOT SECURE FOR PRODUCTION")
            return signature.hex()
        except ImportError:
            logger.error("ecdsa package not installed. Run: pip install ecdsa")
            raise HSMSigningError("ecdsa package not installed. Run: pip install ecdsa")
        except Exception as e:
            logger.error(f"Local signing failed: {e}")
            raise HSMSigningError(f"Local signing failed: {e}")
    
    def _fallback_sign(self, transaction_data: bytes) -> str:
        """Fallback signing method when HSM is disabled"""
        logger.warning("Using fallback signing method - NOT SECURE FOR PRODUCTION")
        return self._local_sign(transaction_data)
    
    def _compute_sha256(self, data: bytes) -> bytes:
        """Compute SHA-256 hash of data"""
        import hashlib
        return hashlib.sha256(data).digest()
    
    def rotate_key(self) -> Dict[str, Any]:
        """
        Rotate the HSM key.
        
        Returns:
            A dictionary with the result of the key rotation
        """
        logger.info(f"Key rotation requested for HSM provider: {self.provider.value}")
        
        if self.provider == HSMProvider.AWS:
            return self._aws_rotate_key()
        elif self.provider == HSMProvider.AZURE:
            return self._azure_rotate_key()
        elif self.provider == HSMProvider.GCP:
            return self._gcp_rotate_key()
        elif self.provider == HSMProvider.THALES:
            return self._thales_rotate_key()
        elif self.provider == HSMProvider.LOCAL:
            return self._local_rotate_key()
        else:
            raise NotImplementedError(f"Key rotation not implemented for {self.provider.value}")
    
    def _aws_rotate_key(self) -> Dict[str, Any]:
        """Rotate AWS KMS key"""
        # Implementation depends on your key rotation policy
        logger.warning("AWS KMS key rotation implementation is application-specific")
        raise NotImplementedError("AWS KMS key rotation implementation is application-specific")
    
    def _azure_rotate_key(self) -> Dict[str, Any]:
        """Rotate Azure Key Vault key"""
        # Implementation depends on your key rotation policy
        logger.warning("Azure Key Vault key rotation implementation is application-specific")
        raise NotImplementedError("Azure Key Vault key rotation implementation is application-specific")
    
    def _gcp_rotate_key(self) -> Dict[str, Any]:
        """Rotate Google Cloud KMS key"""
        # Implementation depends on your key rotation policy
        logger.warning("Google Cloud KMS key rotation implementation is application-specific")
        raise NotImplementedError("Google Cloud KMS key rotation implementation is application-specific")
    
    def _thales_rotate_key(self) -> Dict[str, Any]:
        """Rotate Thales HSM key"""
        # Implementation depends on your key rotation policy
        logger.warning("Thales HSM key rotation implementation is application-specific")
        raise NotImplementedError("Thales HSM key rotation implementation is application-specific")
    
    def _local_rotate_key(self) -> Dict[str, Any]:
        """Rotate local key (development only)"""
        import os
        import ecdsa
        import secrets
        
        # Generate a new private key
        new_private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
        new_private_key_hex = new_private_key.to_string().hex()
        
        # Optionally save to environment variable
        os.environ['DEV_PRIVATE_KEY'] = new_private_key_hex
        
        # Update the client
        self.client['private_key'] = new_private_key_hex
        
        logger.warning("Generated new LOCAL key - NOT SECURE FOR PRODUCTION")
        return {
            "success": True,
            "message": "Local key rotated successfully",
            "public_key": new_private_key.get_verifying_key().to_string().hex()
        }


# Example usage
if __name__ == "__main__":
    hsm = HSM()
    
    # Example transaction data
    transaction = {
        "file_hash": "c97195f3fca2764f95fcdadaf129c6bd0d3612d41cd464eb82d6293b4d3d9109",
        "uploader": "user123",
        "timestamp": 1683403453
    }
    
    # Sign the transaction
    signature = hsm.sign_transaction(json.dumps(transaction))
    print(f"Signature: {signature}") 