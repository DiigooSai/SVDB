# Blockchain Transaction Alerts Setup

## Overview

This document outlines how to set up and configure the enhanced alerting system for SVDB blockchain transactions. The system provides multi-channel alerts for various transaction states and errors, helping you monitor the health of your blockchain integration.

## Alert Channels

The system supports three alert channels:

1. **Email**: Traditional email alerts
2. **Slack**: Real-time notifications in Slack channels
3. **PagerDuty**: Incident management for critical issues

## Setup Instructions

### 1. Configure Environment Variables

Copy the sample configuration file:

```bash
cp alerts-env.sample .env
```

Edit the `.env` file to configure your preferred alert channels:

```
# Alert Configuration
ALERTS_ENABLED=true

# Email Alerts
EMAIL_ALERTS_ENABLED=true
EMAIL_SMTP=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your_email@example.com
EMAIL_PASSWORD=your_password
EMAIL_TO=admin@example.com,oncall@example.com

# Slack Alerts
SLACK_ALERTS_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR_WEBHOOK_URL

# PagerDuty Alerts
PAGERDUTY_ALERTS_ENABLED=true
PAGERDUTY_ROUTING_KEY=your_pagerduty_routing_key
PAGERDUTY_SERVICE_ID=your_service_id
```

### 2. Update Monitoring System

Run the update script to integrate the enhanced alerting with the existing monitoring system:

```bash
python update_monitor.py
```

This script will:
- Create backups of the existing files
- Update the monitoring system to use the new alert configuration
- Modify alert calls to use standardized alert types

### 3. Configure Alert Severities

The system defines several alert types with different severity levels:

| Alert Type | Severity | Description |
|------------|----------|-------------|
| TRANSACTION_SUBMITTED | INFO | Transaction submitted to blockchain |
| TRANSACTION_CONFIRMED | INFO | Transaction confirmed on blockchain |
| TRANSACTION_FAILED | ERROR | Transaction failed and could not be submitted |
| TRANSACTION_REJECTED | ERROR | Transaction rejected by blockchain |
| INSUFFICIENT_FUNDS | CRITICAL | Account has insufficient funds for transaction |
| MAX_RETRIES_EXCEEDED | ERROR | Transaction failed after maximum retry attempts |
| CONSECUTIVE_ERRORS | WARNING | Multiple consecutive errors occurred |
| NONCE_ERROR | WARNING | Transaction nonce mismatch detected |
| GAS_PRICE_ERROR | WARNING | Gas price too low for transaction |

You can customize these alert types in `alert_config.py` to adjust severity levels or add new alert types.

### 4. Test the Alert System

Run a test to verify your alert configuration:

```python
from admin_tools.alert_config import send_alert

# Test alert
send_alert("TRANSACTION_CONFIRMED", {
    "file_hash": "test_hash_123",
    "tx_hash": "0xabcdef1234567890",
    "block_hash": "0x1234567890abcdef"
})
```

### 5. Set Up Monitoring for Alerts

It's recommended to monitor the alert system itself:

1. Check the application logs for any errors in sending alerts
2. Set up a secondary notification if alert sending fails
3. Regularly test alert delivery to ensure all channels are working

## Alert Channel Setup

### Slack Setup

1. Create a Slack app at https://api.slack.com/apps
2. Enable Incoming Webhooks
3. Create a webhook URL for your workspace
4. Copy the webhook URL to your `.env` file

### PagerDuty Setup

1. Create a service in PagerDuty
2. Create an integration with the "Events API v2" integration type
3. Copy the Integration Key (Routing Key) to your `.env` file
4. Set up appropriate escalation policies

## Troubleshooting

Common issues and solutions:

1. **Alerts not sending**
   - Check environment variables are properly set
   - Verify network connectivity to the alert services
   - Check application logs for specific errors

2. **Email authentication failures**
   - For Gmail, you may need to enable "Less secure app access" or use App Passwords
   - Verify SMTP server and port settings

3. **PagerDuty alerts not triggering**
   - Verify the routing key is correct
   - Check that the service ID exists and is properly configured

## Security Considerations

- Store API keys and passwords securely
- Consider using environment variable encryption
- Regularly rotate API keys and passwords
- Limit access to alert configuration files

## Customization

You can extend the alert system by:

1. Adding new alert types in `alert_config.py`
2. Implementing additional alert channels
3. Customizing alert message formats
4. Setting up alert aggregation for high-volume events 