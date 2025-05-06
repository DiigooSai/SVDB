import os
import sys
import time
import json
import logging
import asyncio
import tempfile
import uvicorn
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from fastapi import FastAPI, UploadFile, HTTPException, Depends, BackgroundTasks, File, Header, Query
from fastapi.responses import StreamingResponse, Response, JSONResponse, FileResponse
from pydantic import BaseModel
import io
import sqlite3
import httpx
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Add parent directory to path so we can import verification module
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from verification.verification import SVDBVerifier

try:
    import svdb_core
except ImportError:
    print("Warning: svdb_core not found. Using mock implementation.")
    # Mock implementation for development without Rust module
    class MockSvdbCore:
        @staticmethod
        def py_calculate_hash(data):
            import hashlib
            return hashlib.blake2b(data).hexdigest()
        
        @staticmethod
        def py_store_file(db_path, data):
            hash_val = MockSvdbCore.py_calculate_hash(data)
            # Mock storage
            os.makedirs(os.path.join(db_path, 'data'), exist_ok=True)
            with open(os.path.join(db_path, 'data', hash_val), 'wb') as f:
                f.write(data)
            return hash_val
        
        @staticmethod
        def py_retrieve_file(db_path, hash_val):
            file_path = os.path.join(db_path, 'data', hash_val)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File with hash {file_hash} not found")
            with open(file_path, 'rb') as f:
                return f.read()
    
    svdb_core = MockSvdbCore()

# Load environment variables
load_dotenv()

# Configuration
DB_PATH = os.getenv("SVDB_DB_PATH", "./data")
MONITOR_DB_PATH = os.getenv("SVDB_MONITOR_DB", "./svdb_monitor.db")
ARTHACHAIN_API_URL = os.getenv("ARTHACHAIN_API_URL", "https://api.arthachain.com")
ARTHACHAIN_API_KEY = os.getenv("ARTHACHAIN_API_KEY", "")

app = FastAPI(
    title="SVDB API",
    description="Secure Verified Decentralized Blockchain Database API",
    version="1.0.0"
)

# Add CORS middleware if enabled
if os.getenv("ENABLE_CORS", "false").lower() == "true":
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Data models
class StoreResponse(BaseModel):
    hash: str
    tx_hash: Optional[str] = None
    status: str = "pending"

class VerificationResponse(BaseModel):
    hash: str
    verified: bool
    tx_hash: Optional[str] = None
    block_hash: Optional[str] = None
    timestamp: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

# Blockchain bridge
async def submit_to_blockchain(file_hash: str, metadata: Dict[str, Any]) -> str:
    """Submit a file hash to the blockchain and return transaction hash"""
    payload = {
        "file_hash": file_hash,
        "uploader": metadata.get("uploader", "unknown"),
        "timestamp": int(time.time()),
        "metadata": metadata
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{ARTHACHAIN_API_URL}/api/transactions",
                json=payload,
                headers={"Authorization": f"Bearer {ARTHACHAIN_API_KEY}"}
            )
            response.raise_for_status()
            result = response.json()
            return result.get("tx_hash")
        except httpx.HTTPError as e:
            print(f"Error submitting to blockchain: {e}")
            return None

# Database dependency
def get_db_path():
    os.makedirs(DB_PATH, exist_ok=True)
    return DB_PATH

# Helper to get transaction from monitor database
def get_transaction_by_file_hash(file_hash: str) -> Optional[Dict[str, Any]]:
    """Get transaction details from the monitor database"""
    try:
        with sqlite3.connect(MONITOR_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM transactions WHERE file_hash = ?", (file_hash,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except (sqlite3.Error, FileNotFoundError):
        return None

# Add transaction to monitor database
def add_transaction_to_monitor(file_hash: str, tx_hash: str, metadata: Dict[str, Any]):
    """Add transaction to the monitor database"""
    try:
        os.makedirs(os.path.dirname(MONITOR_DB_PATH), exist_ok=True)
        with sqlite3.connect(MONITOR_DB_PATH) as conn:
            # Create table if it doesn't exist
            conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                file_hash TEXT PRIMARY KEY,
                tx_hash TEXT,
                status TEXT,
                block_hash TEXT,
                timestamp INTEGER,
                retry_count INTEGER DEFAULT 0,
                last_checked INTEGER,
                metadata TEXT
            )
            ''')
            
            conn.execute(
                "INSERT OR REPLACE INTO transactions (file_hash, tx_hash, status, timestamp, last_checked, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (file_hash, tx_hash, "pending", int(time.time()), int(time.time()), json.dumps(metadata))
            )
    except sqlite3.Error as e:
        print(f"Error adding transaction to monitor database: {e}")

# Verify API key if configured
def verify_api_key(api_key: Optional[str] = Header(None)):
    configured_api_key = os.getenv("API_KEY")
    if configured_api_key and api_key != configured_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True

# API Routes
@app.post("/store")
async def store_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    api_key_valid: bool = Depends(verify_api_key)
):
    """
    Store a file in SVDB
    
    The file will be hashed, stored, and the hash will be submitted to the blockchain.
    """
    try:
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Write uploaded file to temporary file
            content = await file.read()
            temp_file.write(content)
            temp_name = temp_file.name
        
        # Get file hash and store file
        file_hash = svdb_core.py_calculate_hash(content)
        db_path = get_db_path()
        
        # Make sure the DB directory exists
        os.makedirs(db_path, exist_ok=True)
        os.makedirs(os.path.join(db_path, "data"), exist_ok=True)
        
        # Store the file
        svdb_core.py_store_file(db_path, content)
        
        # Submit hash to blockchain in background
        tx_hash = None
        if background_tasks:
            background_tasks.add_task(
                submit_to_blockchain_and_update, 
                file_hash=file_hash, 
                metadata={
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": len(content),
                    "timestamp": int(time.time())
                }
            )
            status = "submitted"
        else:
            # If no background tasks available, submit synchronously
            tx_hash = await submit_to_blockchain(
                file_hash, 
                {
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "size": len(content),
                    "timestamp": int(time.time())
                }
            )
            status = "pending" if tx_hash else "error"
        
        return {
            "hash": file_hash,
            "tx_hash": tx_hash,
            "status": status
        }
        
    except Exception as e:
        logger.error(f"Error storing file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error storing file: {str(e)}")

async def submit_to_blockchain_and_update(file_hash: str, metadata: Dict[str, Any]):
    """Background task to submit to blockchain and update local database"""
    tx_hash = await submit_to_blockchain(file_hash, metadata)
    if tx_hash:
        # Add to monitor database
        add_transaction_to_monitor(file_hash, tx_hash, metadata)
        print(f"File {file_hash} submitted to blockchain with tx_hash {tx_hash}")

@app.get("/retrieve/{file_hash}")
async def retrieve_file(
    file_hash: str,
    api_key_valid: bool = Depends(verify_api_key)
):
    """
    Retrieve a file from SVDB by its hash
    """
    try:
        # Get database path
        db_path = get_db_path()
        
        # Retrieve file
        try:
            file_data = svdb_core.py_retrieve_file(db_path, file_hash)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"File with hash {file_hash} not found")
            
        # Get transaction info
        tx_info = get_transaction_by_file_hash(file_hash)
        filename = "file"
        content_type = "application/octet-stream"
        
        if tx_info and "metadata" in tx_info:
            try:
                metadata = json.loads(tx_info["metadata"])
                if "filename" in metadata:
                    filename = metadata["filename"]
                if "content_type" in metadata:
                    content_type = metadata["content_type"]
            except:
                pass
                
        # Return file
        return Response(
            content=file_data,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error retrieving file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")

@app.get("/verify/{file_hash}")
async def verify_file(
    file_hash: str,
    api_key_valid: bool = Depends(verify_api_key)
):
    """
    Verify a file in SVDB
    
    First checks local transaction database, then verifies with blockchain if needed.
    """
    try:
        # Get transaction from local database
        tx_info = get_transaction_by_file_hash(file_hash)
        
        # Prepare response
        response = {
            "hash": file_hash,
            "verified": False,
            "tx_hash": None,
            "block_hash": None,
            "timestamp": None,
            "metadata": {}
        }
        
        # Check if we have the transaction locally
        if tx_info and tx_info.get("status") == "confirmed":
            # Transaction is already confirmed locally
            response["verified"] = True
            response["tx_hash"] = tx_info.get("tx_hash")
            response["block_hash"] = tx_info.get("block_hash")
            response["timestamp"] = tx_info.get("timestamp")
            try:
                response["metadata"] = json.loads(tx_info.get("metadata", "{}"))
            except:
                response["metadata"] = {}
                
        else:
            # Verify with blockchain
            try:
                async with SVDBVerifier() as verifier:
                    verification = await verifier.verify_hash(file_hash)
                    
                    if verification.get("verified"):
                        # Update response with verification info
                        response["verified"] = True
                        response["tx_hash"] = verification.get("tx_hash")
                        response["block_hash"] = verification.get("block_hash")
                        response["timestamp"] = verification.get("timestamp")
                        response["metadata"] = verification.get("metadata", {})
                        
                        # Update local transaction info
                        if tx_info:
                            tx_info["status"] = "confirmed"
                            tx_info["block_hash"] = verification.get("block_hash")
                            
                            # Save updated transaction info
                            db_path = get_db_path()
                            tx_db_path = os.path.join(db_path, "transactions")
                            with open(os.path.join(tx_db_path, f"{file_hash}.json"), "w") as f:
                                json.dump(tx_info, f)
            except Exception as e:
                logger.error(f"Error verifying with blockchain: {str(e)}")
                response["metadata"] = {"error": str(e)}
                
        return response
        
    except Exception as e:
        logger.error(f"Error verifying file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error verifying file: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": app.version
    }

if __name__ == "__main__":
    # Get host and port from environment variables
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    workers = int(os.getenv("API_WORKERS", "1"))
    
    # Run the API server
    uvicorn.run(
        "app:app", 
        host=host, 
        port=port,
        workers=workers,
        reload=os.getenv("DEBUG", "false").lower() == "true"
    ) 