#!/usr/bin/env python3
"""
SVDB Monitor Updater

This script updates the blockchain transaction monitoring system to use the enhanced alert configuration.
"""
import os
import sys
import shutil
from pathlib import Path

# Add parent directory to path for imports
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

def main():
    """Main function to update the monitoring system"""
    
    # Define file paths
    monitor_py_path = os.path.join(os.path.dirname(__file__), 'monitor.py')
    bridge_py_path = os.path.join(parent_dir, 'blockchain_bridge', 'bridge.py')
    
    # Backup files
    backup_monitor = f"{monitor_py_path}.bak"
    backup_bridge = f"{bridge_py_path}.bak"
    
    shutil.copy2(monitor_py_path, backup_monitor)
    shutil.copy2(bridge_py_path, backup_bridge)
    
    print(f"Created backups at {backup_monitor} and {backup_bridge}")
    
    # Update monitor.py to use the new alert_config.py
    with open(monitor_py_path, 'r') as f:
        monitor_content = f.read()
    
    # Replace the import and send_alert references
    updated_monitor = monitor_content.replace(
        "from blockchain_bridge.bridge import BlockchainBridge, send_alert",
        "from blockchain_bridge.bridge import BlockchainBridge\nfrom admin_tools.alert_config import send_alert, ALERT_TYPES"
    )
    
    # Update alert calls in the monitoring system
    updated_monitor = updated_monitor.replace(
        'send_alert("Transaction Confirmed", ',
        'send_alert("TRANSACTION_CONFIRMED", '
    )
    
    updated_monitor = updated_monitor.replace(
        'send_alert("Max Retries Exceeded", ',
        'send_alert("MAX_RETRIES_EXCEEDED", '
    )
    
    # Update bridge.py to use the new alert_config.py
    with open(bridge_py_path, 'r') as f:
        bridge_content = f.read()
    
    # Find the send_alert function in bridge.py and comment it out
    import re
    send_alert_pattern = re.compile(r'def send_alert\([^)]*\):[^}]*?\n\n', re.DOTALL)
    updated_bridge = send_alert_pattern.sub(
        "# send_alert function moved to alert_config.py\n"
        "from admin_tools.alert_config import send_alert, ALERT_TYPES\n\n",
        bridge_content
    )
    
    # Update alert calls in the bridge
    updated_bridge = updated_bridge.replace(
        'send_alert("Insufficient Funds",',
        'send_alert("INSUFFICIENT_FUNDS",'
    )
    
    updated_bridge = updated_bridge.replace(
        'send_alert("Transaction Rejected",',
        'send_alert("TRANSACTION_REJECTED",'
    )
    
    updated_bridge = updated_bridge.replace(
        'send_alert("Max Retries Exceeded",',
        'send_alert("MAX_RETRIES_EXCEEDED",'
    )
    
    updated_bridge = updated_bridge.replace(
        'send_alert("Multiple Consecutive Errors",',
        'send_alert("CONSECUTIVE_ERRORS",'
    )
    
    updated_bridge = updated_bridge.replace(
        'send_alert("Multiple Status Check Errors",',
        'send_alert("CONSECUTIVE_ERRORS",'
    )
    
    # Write the updated files
    with open(monitor_py_path, 'w') as f:
        f.write(updated_monitor)
    
    with open(bridge_py_path, 'w') as f:
        f.write(updated_bridge)
    
    print("Updated monitor.py and bridge.py to use the new alert system")
    print("\nNext steps:")
    print("1. Review the changes and make any necessary adjustments")
    print("2. Configure alerts using the alerts-env.sample template")
    print("3. Test the alert system with different transaction scenarios")
    print("4. Set up monitoring for the alert system itself")

if __name__ == "__main__":
    main() 