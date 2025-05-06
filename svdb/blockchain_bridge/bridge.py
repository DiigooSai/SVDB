import os
import time
import json
import logging
import smtplib
import httpx
from email.mime.text import MIMEText
from typing import Dict, Any, Optional, List, Tuple
from dotenv import load_dotenv
import asyncio
from .hsm import HSM, HSMSigningError, HSMError

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("blockchain_bridge")

# Load environment variables
load_dotenv()

# Configuration
ARTHACHAIN_API_URL = os.getenv("ARTHACHAIN_API_URL", "https://api.arthachain.com")
ARTHACHAIN_API_KEY = os.getenv("ARTHACHAIN_API_KEY", "")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))

# Alert configuration
ALERT_EMAIL_ENABLED = os.getenv("ALERT_EMAIL_ENABLED", "false").lower() == "true"
ALERT_EMAIL_SMTP = os.getenv("ALERT_EMAIL_SMTP", "smtp.gmail.com")
ALERT_EMAIL_PORT = int(os.getenv("ALERT_EMAIL_PORT", "587"))
ALERT_EMAIL_USER = os.getenv("ALERT_EMAIL_USER", "")
ALERT_EMAIL_PASSWORD = os.getenv("ALERT_EMAIL_PASSWORD", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "").split(",")

# Common blockchain error types
class BlockchainError(Exception):
    """Base class for blockchain errors"""
    pass

class InsufficientFundsError(BlockchainError):
    """Raised when account has insufficient funds"""
    pass

class GasPriceTooLowError(BlockchainError):
    """Raised when gas price is too low"""
    pass

class NonceError(BlockchainError):
    """Raised when there's a nonce mismatch"""
    pass

class TransactionRejectedError(BlockchainError):
    """Raised when transaction is rejected by the blockchain"""
    pass

class NetworkError(BlockchainError):
    """Raised when there's a network error"""
    pass

# Utility function to send alerts
def send_alert(subject: str, message: str):
    """Send an alert email"""
    if not ALERT_EMAIL_ENABLED or not ALERT_EMAIL_USER or not ALERT_EMAIL_TO:
        logger.warning(f"Alert not sent (email disabled): {subject}")
        return
    
    try:
        msg = MIMEText(message)
        msg['Subject'] = f"SVDB Alert: {subject}"
        msg['From'] = ALERT_EMAIL_USER
        msg['To'] = ", ".join(ALERT_EMAIL_TO)
        
        server = smtplib.SMTP(ALERT_EMAIL_SMTP, ALERT_EMAIL_PORT)
        server.starttls()
        server.login(ALERT_EMAIL_USER, ALERT_EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Alert email sent: {subject}")
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")

# Function to parse blockchain error responses
def parse_blockchain_error(response_data: Dict[str, Any]) -> Optional[BlockchainError]:
    """Parse blockchain error from response and return appropriate exception"""
    if not response_data or not isinstance(response_data, dict):
        return None
    
    error_message = response_data.get("error", {}).get("message", "")
    
    if "insufficient funds" in error_message.lower():
        return InsufficientFundsError(error_message)
    elif "gas price too low" in error_message.lower() or "fee too low" in error_message.lower():
        return GasPriceTooLowError(error_message)
    elif "nonce" in error_message.lower() and ("mismatch" in error_message.lower() or "incorrect" in error_message.lower()):
        return NonceError(error_message)
    elif "rejected" in error_message.lower():
        return TransactionRejectedError(error_message)
    
    return None

class BlockchainBridge:
    """
    Bridge to interact with ArthaChain blockchain
    """

    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self.api_url = api_url or ARTHACHAIN_API_URL
        self.api_key = api_key or ARTHACHAIN_API_KEY
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.client = httpx.AsyncClient(timeout=30.0)
        self.consecutive_errors = 0
        
        # Initialize HSM for secure transaction signing
        try:
            self.hsm = HSM()
            logger.info("HSM initialized successfully")
        except HSMError as e:
            logger.error(f"Failed to initialize HSM: {e}")
            # Continue without HSM, will use default signing method
            self.hsm = None
            send_alert("HSM Initialization Failed", f"Error initializing HSM: {e}")

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def submit_transaction(self, 
                                file_hash: str, 
                                metadata: Dict[str, Any]) -> Optional[str]:
        """
        Submit a transaction to the blockchain
        
        Args:
            file_hash: The blake3 hash of the file
            metadata: Additional metadata to include
            
        Returns:
            tx_hash: The transaction hash if successful, None otherwise
        """
        payload = {
            "file_hash": file_hash,
            "uploader": metadata.get("uploader", "unknown"),
            "timestamp": int(time.time()),
            "metadata": metadata
        }

        # Sign the transaction payload using HSM
        try:
            # Convert the payload to a JSON string for signing
            payload_str = json.dumps(payload, sort_keys=True)
            
            # Sign using HSM if available
            if self.hsm:
                signature = self.hsm.sign_transaction(payload_str)
                # Add signature to the payload
                payload["signature"] = signature
                logger.info(f"Transaction payload signed with HSM for file hash: {file_hash}")
            else:
                logger.warning(f"HSM not available, submitting unsigned transaction for file hash: {file_hash}")
        except HSMSigningError as e:
            logger.error(f"Failed to sign transaction: {e}")
            send_alert("Transaction Signing Failed", f"Failed to sign transaction for file {file_hash}: {e}")
            # Continue with unsigned transaction if signing fails
            logger.warning(f"Proceeding with unsigned transaction for file hash: {file_hash}")

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.post(
                    f"{self.api_url}/api/transactions",
                    json=payload,
                    headers=self.headers
                )
                
                # Reset consecutive errors on success
                if response.status_code < 400:
                    self.consecutive_errors = 0
                
                # Handle errors based on response
                if response.status_code >= 400:
                    response_data = response.json() if response.headers.get("content-type") == "application/json" else {}
                    blockchain_error = parse_blockchain_error(response_data)
                    
                    if blockchain_error:
                        if isinstance(blockchain_error, InsufficientFundsError):
                            logger.critical(f"Insufficient funds error: {blockchain_error}")
                            send_alert("Insufficient Funds", f"Transaction for {file_hash} failed: insufficient funds")
                            return None  # Don't retry for fund issues
                        
                        elif isinstance(blockchain_error, GasPriceTooLowError):
                            logger.warning(f"Gas price too low (attempt {attempt+1}/{MAX_RETRIES}): {blockchain_error}")
                            # Continue to retry with exponential backoff
                        
                        elif isinstance(blockchain_error, NonceError):
                            logger.warning(f"Nonce mismatch (attempt {attempt+1}/{MAX_RETRIES}): {blockchain_error}")
                            # Nonce issues often resolve with a retry
                        
                        elif isinstance(blockchain_error, TransactionRejectedError):
                            logger.error(f"Transaction rejected: {blockchain_error}")
                            send_alert("Transaction Rejected", f"Transaction for {file_hash} was rejected by the blockchain")
                            return None  # Don't retry rejected transactions
                        
                        raise blockchain_error
                
                response.raise_for_status()
                result = response.json()
                tx_hash = result.get("tx_hash")
                logger.info(f"Transaction submitted successfully: {tx_hash}")
                return tx_hash
                
            except (BlockchainError, httpx.HTTPError) as e:
                # Track consecutive errors for alerting
                self.consecutive_errors += 1
                
                # Send alert if too many consecutive errors
                if self.consecutive_errors >= 5:
                    send_alert("Multiple Consecutive Errors", 
                              f"Encountered {self.consecutive_errors} consecutive errors. Last error: {str(e)}")
                
                logger.error(f"Error submitting transaction (attempt {attempt+1}/{MAX_RETRIES}): {e}")
                
                if attempt < MAX_RETRIES - 1:
                    # Exponential backoff
                    wait_time = RETRY_DELAY * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
            
        # All retries failed
        logger.critical(f"Failed to submit transaction after {MAX_RETRIES} attempts for file_hash: {file_hash}")
        send_alert("Transaction Submission Failed", 
                  f"Failed to submit transaction after {MAX_RETRIES} attempts for file hash: {file_hash}")
        return None

    async def get_transaction_status(self, tx_hash: str) -> Dict[str, Any]:
        """
        Get the status of a transaction
        
        Args:
            tx_hash: The transaction hash
            
        Returns:
            Dictionary with transaction status information
        """
        try:
            response = await self.client.get(
                f"{self.api_url}/api/transactions/{tx_hash}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            self.consecutive_errors += 1
            
            # Send alert if too many consecutive errors
            if self.consecutive_errors >= 5:
                send_alert("Multiple Status Check Errors", 
                          f"Encountered {self.consecutive_errors} consecutive errors checking transaction status")
            
            logger.error(f"Error getting transaction status: {e}")
            return {
                "tx_hash": tx_hash,
                "status": "error",
                "error": str(e)
            }

    async def verify_file_hash(self, file_hash: str) -> Dict[str, Any]:
        """
        Verify if a file hash exists on the blockchain
        
        Args:
            file_hash: The blake3 hash of the file
            
        Returns:
            Dictionary with verification information
        """
        try:
            response = await self.client.get(
                f"{self.api_url}/api/verify/{file_hash}",
                headers=self.headers
            )
            response.raise_for_status()
            result = response.json()
            
            # Reset consecutive errors on success
            self.consecutive_errors = 0
            
            return {
                "verified": result.get("verified", False),
                "tx_hash": result.get("tx_hash"),
                "block_hash": result.get("block_hash"),
                "timestamp": result.get("timestamp"),
                "metadata": result.get("metadata")
            }
        except httpx.HTTPError as e:
            self.consecutive_errors += 1
            
            # Send alert if too many consecutive errors
            if self.consecutive_errors >= 5:
                send_alert("Multiple Verification Errors", 
                          f"Encountered {self.consecutive_errors} consecutive errors verifying file hashes")
            
            logger.error(f"Error verifying file hash: {e}")
            return {
                "verified": False,
                "error": str(e)
            }

    async def decode_hex_data(self, hex_data: str) -> Dict[str, Any]:
        """
        Decode hexadecimal data from the blockchain
        
        Args:
            hex_data: Hexadecimal data string
            
        Returns:
            Decoded data as dictionary
        """
        try:
            # Remove '0x' prefix if present
            if hex_data.startswith('0x'):
                hex_data = hex_data[2:]
                
            # Convert hex to bytes and then to string
            byte_data = bytes.fromhex(hex_data)
            try:
                # Try to decode as UTF-8 and parse as JSON
                json_str = byte_data.decode('utf-8')
                return json.loads(json_str)
            except (UnicodeDecodeError, json.JSONDecodeError):
                # If not valid JSON, return raw data
                return {"raw_data": byte_data.hex()}
        except Exception as e:
            logger.error(f"Error decoding hex data: {e}")
            return {"error": str(e)}

    async def check_confirmation_status(self, tx_hash: str) -> Dict[str, Any]:
        """
        Check the confirmation status of a transaction
        
        Args:
            tx_hash: Transaction hash
            
        Returns:
            Dictionary with confirmation details
        """
        tx_status = await self.get_transaction_status(tx_hash)
        status = tx_status.get("status", "unknown")
        block_hash = tx_status.get("block_hash")
        block_number = tx_status.get("block_number")
        confirmations = tx_status.get("confirmations", 0)
        
        # Check if transaction is confirmed
        is_confirmed = status == "confirmed" and block_hash and confirmations > 0
        
        return {
            "tx_hash": tx_hash,
            "status": status,
            "block_hash": block_hash,
            "block_number": block_number,
            "confirmations": confirmations,
            "is_confirmed": is_confirmed,
            "timestamp": tx_status.get("timestamp")
        }

    async def batch_submit(self, 
                          file_data: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, Optional[str]]:
        """
        Submit multiple transactions to the blockchain in batch
        
        Args:
            file_data: List of tuples containing (file_hash, metadata)
            
        Returns:
            Dictionary mapping file_hash to tx_hash
        """
        results = {}
        
        async def submit_single(file_hash, metadata):
            tx_hash = await self.submit_transaction(file_hash, metadata)
            results[file_hash] = tx_hash
            
        tasks = [submit_single(file_hash, metadata) for file_hash, metadata in file_data]
        await asyncio.gather(*tasks)
        return results

    async def rotate_signing_key(self) -> Dict[str, Any]:
        """
        Rotate the signing key used for transactions.
        
        Returns:
            Dict with status information
        """
        try:
            if not self.hsm:
                logger.error("Cannot rotate key: HSM not initialized")
                return {"success": False, "message": "HSM not initialized"}
            
            # Request key rotation from HSM
            result = self.hsm.rotate_key()
            logger.info("Signing key rotated successfully")
            
            # Send alert about key rotation
            send_alert("Signing Key Rotated", "Blockchain transaction signing key was rotated successfully.")
            
            return {"success": True, "message": "Key rotated successfully"}
        except Exception as e:
            logger.error(f"Failed to rotate signing key: {e}")
            send_alert("Key Rotation Failed", f"Failed to rotate blockchain signing key: {e}")
            return {"success": False, "message": str(e)}

# For testing and command-line usage
async def main():
    import asyncio
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python bridge.py <command> [args]")
        print("Commands:")
        print("  submit <file_hash> <metadata_json>")
        print("  verify <file_hash>")
        print("  status <tx_hash>")
        print("  confirm <tx_hash>")
        print("  decode <hex_data>")
        print("  alert <subject> <message>")
        return
    
    command = sys.argv[1]
    async with BlockchainBridge() as bridge:
        if command == "submit" and len(sys.argv) >= 4:
            file_hash = sys.argv[2]
            metadata = json.loads(sys.argv[3])
            tx_hash = await bridge.submit_transaction(file_hash, metadata)
            print(f"Transaction submitted: {tx_hash}")
        
        elif command == "verify" and len(sys.argv) >= 3:
            file_hash = sys.argv[2]
            result = await bridge.verify_file_hash(file_hash)
            print(json.dumps(result, indent=2))
        
        elif command == "status" and len(sys.argv) >= 3:
            tx_hash = sys.argv[2]
            result = await bridge.get_transaction_status(tx_hash)
            print(json.dumps(result, indent=2))
            
        elif command == "confirm" and len(sys.argv) >= 3:
            tx_hash = sys.argv[2]
            result = await bridge.check_confirmation_status(tx_hash)
            print(json.dumps(result, indent=2))
            
        elif command == "decode" and len(sys.argv) >= 3:
            hex_data = sys.argv[2]
            result = await bridge.decode_hex_data(hex_data)
            print(json.dumps(result, indent=2))
            
        elif command == "alert" and len(sys.argv) >= 4:
            subject = sys.argv[2]
            message = sys.argv[3]
            send_alert(subject, message)
            print("Alert sent")
        
        else:
            print("Invalid command or arguments")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 