#!/usr/bin/env python3
"""
SVDB Transaction Monitor

This script monitors and updates blockchain transaction statuses.
It periodically checks pending transactions and updates their status in the database.
"""
import os
import sys
import json
import time
import sqlite3
import logging
import argparse
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from blockchain_bridge.bridge import BlockchainBridge, send_alert

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'monitor.log'))
    ]
)
logger = logging.getLogger("svdb.monitor")

# Environment variables
MONITOR_DB_PATH = os.getenv("SVDB_MONITOR_DB", "./svdb_monitor.db")
CHECK_INTERVAL = int(os.getenv("SVDB_MONITOR_INTERVAL", "300"))  # 5 minutes default
MAX_RETRIES = int(os.getenv("SVDB_MAX_RETRIES", "3"))

class TransactionMonitor:
    """Monitor for blockchain transactions"""
    
    def __init__(self, db_path: str):
        """
        Initialize the transaction monitor
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.setup_database()
    
    def setup_database(self):
        """Set up the monitor database"""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create transactions table if it doesn't exist
            cursor.execute('''
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
            
            # Create index on status for faster filtering
            cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_status ON transactions(status)
            ''')
            
            conn.commit()
            conn.close()
            
            logger.info(f"Database setup complete at {self.db_path}")
        
        except sqlite3.Error as e:
            logger.error(f"Database setup error: {e}")
            raise
    
    def get_pending_transactions(self) -> List[Dict[str, Any]]:
        """
        Get all pending transactions from the database
        
        Returns:
            List of pending transaction dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get transactions with status 'pending'
            cursor.execute("SELECT * FROM transactions WHERE status = 'pending'")
            
            # Convert rows to dictionaries
            rows = cursor.fetchall()
            transactions = [dict(row) for row in rows]
            
            conn.close()
            
            logger.info(f"Found {len(transactions)} pending transactions")
            return transactions
        
        except sqlite3.Error as e:
            logger.error(f"Error getting pending transactions: {e}")
            return []
    
    def get_failed_transactions(self) -> List[Dict[str, Any]]:
        """
        Get all failed transactions from the database
        
        Returns:
            List of failed transaction dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get transactions with status 'failed' or 'error'
            cursor.execute("SELECT * FROM transactions WHERE status IN ('failed', 'error')")
            
            # Convert rows to dictionaries
            rows = cursor.fetchall()
            transactions = [dict(row) for row in rows]
            
            conn.close()
            
            logger.info(f"Found {len(transactions)} failed transactions")
            return transactions
        
        except sqlite3.Error as e:
            logger.error(f"Error getting failed transactions: {e}")
            return []
    
    def update_transaction(self, file_hash: str, updates: Dict[str, Any]):
        """
        Update a transaction in the database
        
        Args:
            file_hash: File hash of the transaction to update
            updates: Dictionary of field updates
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build the SET clause
            set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
            values = list(updates.values())
            values.append(file_hash)
            
            # Update the transaction
            cursor.execute(f"UPDATE transactions SET {set_clause} WHERE file_hash = ?", values)
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated transaction {file_hash}: {updates}")
        
        except sqlite3.Error as e:
            logger.error(f"Error updating transaction {file_hash}: {e}")
    
    async def check_transaction_status(self, tx_hash: str, file_hash: str, retry_count: int) -> Dict[str, Any]:
        """
        Check the status of a transaction on the blockchain
        
        Args:
            tx_hash: Transaction hash to check
            file_hash: File hash (for logging)
            retry_count: Current retry count
            
        Returns:
            Dictionary with updated transaction status
        """
        try:
            async with BlockchainBridge() as bridge:
                status = await bridge.check_confirmation_status(tx_hash)
                logger.info(f"Transaction {tx_hash} status: {status.get('status', 'unknown')}")
                
                updates = {
                    "last_checked": int(time.time())
                }
                
                if status.get("is_confirmed", False):
                    updates["status"] = "confirmed"
                    updates["block_hash"] = status.get("block_hash")
                    
                    # Send notification
                    logger.info(f"Transaction {tx_hash} for file {file_hash} confirmed!")
                    
                    try:
                        # Send alert for confirmation
                        send_alert(
                            "Transaction Confirmed", 
                            f"Transaction {tx_hash} for file {file_hash} has been confirmed on the blockchain!"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send confirmation alert: {e}")
                
                return updates
        
        except Exception as e:
            logger.error(f"Error checking transaction status {tx_hash}: {e}")
            
            # If we've exceeded retry count, mark as failed
            if retry_count >= MAX_RETRIES:
                logger.error(f"Max retries exceeded for {tx_hash}, marking as failed")
                return {
                    "status": "failed",
                    "last_checked": int(time.time())
                }
            
            return {
                "last_checked": int(time.time())
            }
    
    async def retry_transaction(self, file_hash: str, metadata: Dict[str, Any], retry_count: int) -> Dict[str, Any]:
        """
        Retry a failed transaction
        
        Args:
            file_hash: File hash to retry
            metadata: Transaction metadata
            retry_count: Current retry count
            
        Returns:
            Dictionary with updated transaction status
        """
        # Parse metadata if it's a string
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        
        try:
            async with BlockchainBridge() as bridge:
                tx_hash = await bridge.submit_transaction(file_hash, metadata)
                
                if tx_hash:
                    logger.info(f"Successfully resubmitted transaction for {file_hash}: {tx_hash}")
                    return {
                        "tx_hash": tx_hash,
                        "status": "pending",
                        "retry_count": retry_count + 1,
                        "last_checked": int(time.time())
                    }
                else:
                    logger.error(f"Failed to resubmit transaction for {file_hash}")
                    return {
                        "status": "error",
                        "retry_count": retry_count + 1,
                        "last_checked": int(time.time())
                    }
        
        except Exception as e:
            logger.error(f"Error retrying transaction for {file_hash}: {e}")
            return {
                "status": "error",
                "retry_count": retry_count + 1,
                "last_checked": int(time.time())
            }
    
    async def process_pending_transactions(self):
        """Process all pending transactions"""
        pending_transactions = self.get_pending_transactions()
        
        for tx in pending_transactions:
            file_hash = tx["file_hash"]
            tx_hash = tx["tx_hash"]
            
            if not tx_hash:
                logger.warning(f"Transaction {file_hash} has no tx_hash, skipping")
                continue
            
            # Check transaction status
            retry_count = tx.get("retry_count", 0)
            updates = await self.check_transaction_status(tx_hash, file_hash, retry_count)
            
            # Update transaction in database
            if updates:
                self.update_transaction(file_hash, updates)
    
    async def process_failed_transactions(self):
        """Retry failed transactions"""
        failed_transactions = self.get_failed_transactions()
        
        for tx in failed_transactions:
            file_hash = tx["file_hash"]
            retry_count = tx.get("retry_count", 0)
            metadata = tx.get("metadata", "{}")
            
            # Skip if we've exceeded max retries
            if retry_count >= MAX_RETRIES:
                logger.warning(f"Transaction {file_hash} has exceeded max retries, skipping")
                continue
            
            # Retry transaction
            updates = await self.retry_transaction(file_hash, metadata, retry_count)
            
            # Update transaction in database
            if updates:
                self.update_transaction(file_hash, updates)
    
    async def run_once(self):
        """Run the monitor once"""
        logger.info("Starting transaction check...")
        
        try:
            await self.process_pending_transactions()
            await self.process_failed_transactions()
        except Exception as e:
            logger.error(f"Error in monitor run: {e}")
        
        logger.info("Transaction check complete")
    
    async def run_forever(self, interval: int = CHECK_INTERVAL):
        """
        Run the monitor indefinitely
        
        Args:
            interval: Check interval in seconds
        """
        logger.info(f"Starting monitor with {interval}s interval")
        
        try:
            while True:
                await self.run_once()
                logger.info(f"Sleeping for {interval} seconds...")
                await asyncio.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
        except Exception as e:
            logger.error(f"Monitor error: {e}")
            # Send alert for monitor error
            try:
                send_alert("Monitor Error", f"Transaction monitor encountered an error: {e}")
            except Exception:
                pass
            raise

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="SVDB Transaction Monitor")
    parser.add_argument(
        "--db-path",
        help=f"Path to the monitor database (default: {MONITOR_DB_PATH})"
    )
    parser.add_argument(
        "--interval",
        type=int,
        help=f"Check interval in seconds (default: {CHECK_INTERVAL})"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run the monitor once and exit"
    )
    parser.add_argument(
        "--alert-test",
        action="store_true",
        help="Send a test alert"
    )
    
    args = parser.parse_args()
    
    # Send test alert if requested
    if args.alert_test:
        try:
            send_alert("Test Alert", "This is a test alert from SVDB Monitor")
            logger.info("Test alert sent")
        except Exception as e:
            logger.error(f"Failed to send test alert: {e}")
        return
    
    # Get database path
    db_path = args.db_path or MONITOR_DB_PATH
    
    # Create monitor
    monitor = TransactionMonitor(db_path)
    
    # Run once or forever
    if args.run_once:
        await monitor.run_once()
    else:
        # Get interval
        interval = args.interval or CHECK_INTERVAL
        await monitor.run_forever(interval)

if __name__ == "__main__":
    asyncio.run(main()) 