"""
SVDB Verification Module

This module handles verification of file hashes on the blockchain.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("svdb.verification")

# Import blockchain bridge
import sys
from pathlib import Path
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from blockchain_bridge.bridge import BlockchainBridge

class SVDBVerifier:
    """
    SVDBVerifier is responsible for verifying file hashes on the blockchain
    """
    
    def __init__(self):
        """Initialize the verifier with a blockchain bridge"""
        self.bridge = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.bridge = BlockchainBridge()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.bridge:
            await self.bridge.close()
    
    async def verify_hash(self, file_hash: str) -> Dict[str, Any]:
        """
        Verify a file hash on the blockchain
        
        Args:
            file_hash: The hash to verify
            
        Returns:
            Dict containing verification results
        """
        if not self.bridge:
            raise RuntimeError("SVDBVerifier must be used as an async context manager")
        
        try:
            # Verify hash on the blockchain
            verification = await self.bridge.verify_file_hash(file_hash)
            
            if verification.get("verified"):
                # If verified, get more details
                tx_hash = verification.get("tx_hash")
                
                if tx_hash:
                    # Get confirmation status
                    confirmation = await self.bridge.check_confirmation_status(tx_hash)
                    
                    # Update verification with confirmation details
                    verification["block_hash"] = confirmation.get("block_hash")
                    verification["block_number"] = confirmation.get("block_number")
                    verification["confirmations"] = confirmation.get("confirmations")
                    verification["timestamp"] = confirmation.get("timestamp")
            
            return verification
            
        except Exception as e:
            logger.error(f"Error verifying hash: {str(e)}")
            return {
                "verified": False,
                "error": str(e)
            }

# For testing and command-line usage
async def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python verification.py <file_hash>")
        return
        
    file_hash = sys.argv[1]
    
    async with SVDBVerifier() as verifier:
        result = await verifier.verify_hash(file_hash)
        
        import json
        print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main()) 