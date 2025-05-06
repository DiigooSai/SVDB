#!/usr/bin/env python3
"""
SVDB Alert Configuration

This module configures comprehensive blockchain transaction failure alerts.
"""
import os
import json
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("svdb.alerts")

# Alert Configuration
ALERTS_ENABLED = os.getenv("ALERTS_ENABLED", "true").lower() == "true"

# Email Alerts
EMAIL_ALERTS_ENABLED = os.getenv("EMAIL_ALERTS_ENABLED", "false").lower() == "true"
EMAIL_SMTP = os.getenv("EMAIL_SMTP", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_TO = os.getenv("EMAIL_TO", "").split(",")

# Slack Alerts
SLACK_ALERTS_ENABLED = os.getenv("SLACK_ALERTS_ENABLED", "false").lower() == "true"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Pagerduty Alerts
PAGERDUTY_ALERTS_ENABLED = os.getenv("PAGERDUTY_ALERTS_ENABLED", "false").lower() == "true"
PAGERDUTY_ROUTING_KEY = os.getenv("PAGERDUTY_ROUTING_KEY", "")
PAGERDUTY_SERVICE_ID = os.getenv("PAGERDUTY_SERVICE_ID", "")

# Alert Severity Levels
class AlertSeverity:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

# Transaction Alert Types
ALERT_TYPES = {
    "TRANSACTION_SUBMITTED": {
        "title": "Transaction Submitted",
        "severity": AlertSeverity.INFO,
        "description": "Transaction submitted to blockchain"
    },
    "TRANSACTION_CONFIRMED": {
        "title": "Transaction Confirmed",
        "severity": AlertSeverity.INFO,
        "description": "Transaction confirmed on blockchain"
    },
    "TRANSACTION_FAILED": {
        "title": "Transaction Failed",
        "severity": AlertSeverity.ERROR,
        "description": "Transaction failed and could not be submitted"
    },
    "TRANSACTION_REJECTED": {
        "title": "Transaction Rejected",
        "severity": AlertSeverity.ERROR,
        "description": "Transaction rejected by blockchain"
    },
    "INSUFFICIENT_FUNDS": {
        "title": "Insufficient Funds",
        "severity": AlertSeverity.CRITICAL,
        "description": "Account has insufficient funds for transaction"
    },
    "MAX_RETRIES_EXCEEDED": {
        "title": "Max Retries Exceeded",
        "severity": AlertSeverity.ERROR,
        "description": "Transaction failed after maximum retry attempts"
    },
    "CONSECUTIVE_ERRORS": {
        "title": "Consecutive Errors",
        "severity": AlertSeverity.WARNING,
        "description": "Multiple consecutive errors occurred"
    },
    "NONCE_ERROR": {
        "title": "Nonce Error",
        "severity": AlertSeverity.WARNING,
        "description": "Transaction nonce mismatch detected"
    },
    "GAS_PRICE_ERROR": {
        "title": "Gas Price Error",
        "severity": AlertSeverity.WARNING,
        "description": "Gas price too low for transaction"
    }
}

def send_email_alert(alert_type: str, details: Dict[str, Any]):
    """Send alert via email"""
    if not EMAIL_ALERTS_ENABLED or not EMAIL_USER or not EMAIL_TO:
        logger.warning(f"Email alerts disabled or not configured. Alert not sent: {alert_type}")
        return
    
    alert_config = ALERT_TYPES.get(alert_type, {
        "title": "Unknown Alert",
        "severity": AlertSeverity.INFO,
        "description": "Unknown alert type"
    })
    
    try:
        # Create message
        message = f"""
SVDB Alert: {alert_config['title']}
Severity: {alert_config['severity'].upper()}
Time: {details.get('timestamp', 'N/A')}

{alert_config['description']}

Details:
{json.dumps(details, indent=2)}
        """
        
        msg = MIMEText(message)
        msg['Subject'] = f"SVDB Alert: {alert_config['title']} - {alert_config['severity'].upper()}"
        msg['From'] = EMAIL_USER
        msg['To'] = ", ".join(EMAIL_TO)
        
        # Send email
        server = smtplib.SMTP(EMAIL_SMTP, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email alert sent: {alert_type}")
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")

def send_slack_alert(alert_type: str, details: Dict[str, Any]):
    """Send alert to Slack"""
    if not SLACK_ALERTS_ENABLED or not SLACK_WEBHOOK_URL:
        logger.warning(f"Slack alerts disabled or not configured. Alert not sent: {alert_type}")
        return
    
    alert_config = ALERT_TYPES.get(alert_type, {
        "title": "Unknown Alert",
        "severity": AlertSeverity.INFO,
        "description": "Unknown alert type"
    })
    
    # Set color based on severity
    color_map = {
        AlertSeverity.INFO: "#36a64f",  # green
        AlertSeverity.WARNING: "#ffcc00",  # yellow
        AlertSeverity.ERROR: "#ff9900",  # orange
        AlertSeverity.CRITICAL: "#ff0000"  # red
    }
    color = color_map.get(alert_config['severity'], "#808080")  # gray default
    
    try:
        # Create message payload
        payload = {
            "attachments": [
                {
                    "fallback": f"SVDB Alert: {alert_config['title']}",
                    "color": color,
                    "title": f"SVDB Alert: {alert_config['title']}",
                    "text": alert_config['description'],
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert_config['severity'].upper(),
                            "short": True
                        }
                    ],
                    "footer": "SVDB Transaction Monitor",
                    "ts": details.get('timestamp', int(time.time()))
                }
            ]
        }
        
        # Add detail fields from the details dict
        for key, value in details.items():
            if key != 'timestamp':  # Skip timestamp as it's used above
                payload['attachments'][0]['fields'].append({
                    "title": key,
                    "value": str(value),
                    "short": True
                })
        
        # Send to Slack
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        
        logger.info(f"Slack alert sent: {alert_type}")
    except Exception as e:
        logger.error(f"Failed to send Slack alert: {e}")

def send_pagerduty_alert(alert_type: str, details: Dict[str, Any]):
    """Send alert to PagerDuty"""
    if not PAGERDUTY_ALERTS_ENABLED or not PAGERDUTY_ROUTING_KEY:
        logger.warning(f"PagerDuty alerts disabled or not configured. Alert not sent: {alert_type}")
        return
    
    alert_config = ALERT_TYPES.get(alert_type, {
        "title": "Unknown Alert",
        "severity": AlertSeverity.INFO,
        "description": "Unknown alert type"
    })
    
    # Map severity to PagerDuty severity
    severity_map = {
        AlertSeverity.INFO: "info",
        AlertSeverity.WARNING: "warning",
        AlertSeverity.ERROR: "error",
        AlertSeverity.CRITICAL: "critical"
    }
    severity = severity_map.get(alert_config['severity'], "info")
    
    try:
        # Create payload
        payload = {
            "routing_key": PAGERDUTY_ROUTING_KEY,
            "event_action": "trigger",
            "payload": {
                "summary": f"SVDB Alert: {alert_config['title']}",
                "source": "SVDB Transaction Monitor",
                "severity": severity,
                "custom_details": details
            }
        }
        
        # Add service if specified
        if PAGERDUTY_SERVICE_ID:
            payload["payload"]["service"] = PAGERDUTY_SERVICE_ID
        
        # Send to PagerDuty
        response = requests.post(
            "https://events.pagerduty.com/v2/enqueue", 
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        logger.info(f"PagerDuty alert sent: {alert_type}")
    except Exception as e:
        logger.error(f"Failed to send PagerDuty alert: {e}")

def send_alert(alert_type: str, details: Dict[str, Any]):
    """
    Send alert to all configured channels
    
    Args:
        alert_type: Type of alert (must be defined in ALERT_TYPES)
        details: Dictionary of alert details
    """
    if not ALERTS_ENABLED:
        logger.info(f"Alerts disabled. Alert not sent: {alert_type}")
        return
    
    if alert_type not in ALERT_TYPES:
        logger.warning(f"Unknown alert type: {alert_type}")
    
    logger.info(f"Sending alert: {alert_type}")
    
    # Add timestamp if not present
    if 'timestamp' not in details:
        details['timestamp'] = int(time.time())
    
    # Send to all configured channels
    if EMAIL_ALERTS_ENABLED:
        send_email_alert(alert_type, details)
    
    if SLACK_ALERTS_ENABLED:
        send_slack_alert(alert_type, details)
    
    if PAGERDUTY_ALERTS_ENABLED:
        send_pagerduty_alert(alert_type, details) 