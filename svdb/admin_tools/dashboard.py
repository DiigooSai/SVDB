#!/usr/bin/env python3
"""
SVDB Admin Dashboard
A simple web dashboard for monitoring SVDB transactions
"""
import os
import sys
import json
import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Add parent directory to path for imports
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import blockchain components
from blockchain_bridge.bridge import BlockchainBridge

# Load environment variables
load_dotenv()

# Configure app
app = FastAPI(title="SVDB Admin Dashboard", description="Admin Dashboard for SVDB")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create templates directory if it doesn't exist
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)

# Set up templates
templates = Jinja2Templates(directory=str(templates_dir))

# Create base template file if it doesn't exist
base_template_path = templates_dir / "base.html"
if not base_template_path.exists():
    with open(base_template_path, "w") as f:
        f.write("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}SVDB Admin Dashboard{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .dashboard-container { padding: 20px; }
        .status-pending { color: orange; }
        .status-confirmed { color: green; }
        .status-failed { color: red; }
        .status-error { color: darkred; }
        .status-unknown { color: gray; }
    </style>
    {% block extra_head %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="/">SVDB Admin Dashboard</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="/">Transactions</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/status">System Status</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/retry">Retry Failed</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="dashboard-container">
        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
        """)

# Create dashboard template
dashboard_template_path = templates_dir / "dashboard.html"
if not dashboard_template_path.exists():
    with open(dashboard_template_path, "w") as f:
        f.write("""
{% extends "base.html" %}

{% block title %}SVDB Transaction Dashboard{% endblock %}

{% block content %}
<h1>Transaction Dashboard</h1>

<div class="row mb-4">
    <div class="col-md-3">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Total Transactions</h5>
                <p class="card-text display-4">{{ stats.total }}</p>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Confirmed</h5>
                <p class="card-text display-4 status-confirmed">{{ stats.confirmed }}</p>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Pending</h5>
                <p class="card-text display-4 status-pending">{{ stats.pending }}</p>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Failed/Error</h5>
                <p class="card-text display-4 status-failed">{{ stats.failed }}</p>
            </div>
        </div>
    </div>
</div>

<div class="row mb-3">
    <div class="col">
        <form method="GET" action="/" class="row g-3">
            <div class="col-md-4">
                <select name="status" class="form-select">
                    <option value="all" {% if filter_status == 'all' %}selected{% endif %}>All Statuses</option>
                    <option value="pending" {% if filter_status == 'pending' %}selected{% endif %}>Pending</option>
                    <option value="confirmed" {% if filter_status == 'confirmed' %}selected{% endif %}>Confirmed</option>
                    <option value="failed" {% if filter_status == 'failed' %}selected{% endif %}>Failed</option>
                    <option value="error" {% if filter_status == 'error' %}selected{% endif %}>Error</option>
                </select>
            </div>
            <div class="col-md-6">
                <input type="text" name="search" class="form-control" placeholder="Search by hash..." value="{{ search_query }}">
            </div>
            <div class="col-md-2">
                <button type="submit" class="btn btn-primary w-100">Filter</button>
            </div>
        </form>
    </div>
</div>

<div class="table-responsive">
    <table class="table table-striped table-hover">
        <thead>
            <tr>
                <th>File Hash</th>
                <th>Transaction Hash</th>
                <th>Status</th>
                <th>Timestamp</th>
                <th>Last Checked</th>
                <th>Retry Count</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for tx in transactions %}
            <tr>
                <td><span title="{{ tx.file_hash }}">{{ tx.file_hash[:10] }}...</span></td>
                <td>
                    {% if tx.tx_hash %}
                    <span title="{{ tx.tx_hash }}">{{ tx.tx_hash[:10] }}...</span>
                    {% else %}
                    <span class="text-muted">N/A</span>
                    {% endif %}
                </td>
                <td class="status-{{ tx.status }}">{{ tx.status }}</td>
                <td>{{ tx.timestamp_formatted }}</td>
                <td>{{ tx.last_checked_formatted }}</td>
                <td>{{ tx.retry_count }}</td>
                <td>
                    <div class="btn-group" role="group">
                        <a href="/transaction/{{ tx.file_hash }}" class="btn btn-sm btn-primary">Details</a>
                        {% if tx.status in ['failed', 'error'] %}
                        <a href="/retry/{{ tx.file_hash }}" class="btn btn-sm btn-warning">Retry</a>
                        {% endif %}
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

{% if not transactions %}
<div class="alert alert-info">No transactions found matching your criteria.</div>
{% endif %}

{% endblock %}
        """)

# Create transaction detail template
tx_detail_template_path = templates_dir / "transaction_detail.html"
if not tx_detail_template_path.exists():
    with open(tx_detail_template_path, "w") as f:
        f.write("""
{% extends "base.html" %}

{% block title %}Transaction Details{% endblock %}

{% block content %}
<div class="row mb-3">
    <div class="col">
        <a href="/" class="btn btn-secondary">&larr; Back to Dashboard</a>
    </div>
</div>

<h1>Transaction Details</h1>

{% if tx %}
<div class="card mb-4">
    <div class="card-header">
        <h5>Basic Information</h5>
    </div>
    <div class="card-body">
        <div class="row">
            <div class="col-md-6">
                <p><strong>File Hash:</strong> <span class="text-break">{{ tx.file_hash }}</span></p>
                <p><strong>Transaction Hash:</strong> <span class="text-break">{{ tx.tx_hash or 'N/A' }}</span></p>
                <p><strong>Status:</strong> <span class="status-{{ tx.status }}">{{ tx.status }}</span></p>
                <p><strong>Timestamp:</strong> {{ tx.timestamp_formatted }}</p>
            </div>
            <div class="col-md-6">
                <p><strong>Block Hash:</strong> <span class="text-break">{{ tx.block_hash or 'N/A' }}</span></p>
                <p><strong>Retry Count:</strong> {{ tx.retry_count }}</p>
                <p><strong>Last Checked:</strong> {{ tx.last_checked_formatted }}</p>
                {% if blockchain_status %}
                <p><strong>Confirmations:</strong> {{ blockchain_status.confirmations or 0 }}</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>

{% if metadata %}
<div class="card mb-4">
    <div class="card-header">
        <h5>Metadata</h5>
    </div>
    <div class="card-body">
        <pre class="bg-light p-3 rounded"><code>{{ metadata_json }}</code></pre>
    </div>
</div>
{% endif %}

{% if blockchain_status %}
<div class="card mb-4">
    <div class="card-header">
        <h5>Blockchain Status</h5>
    </div>
    <div class="card-body">
        <pre class="bg-light p-3 rounded"><code>{{ blockchain_status_json }}</code></pre>
    </div>
</div>
{% endif %}

<div class="row mt-4">
    <div class="col">
        <div class="btn-group" role="group">
            <a href="/retry/{{ tx.file_hash }}" class="btn btn-warning">Retry Transaction</a>
            <a href="/refresh/{{ tx.file_hash }}" class="btn btn-info">Refresh Status</a>
        </div>
    </div>
</div>
{% else %}
<div class="alert alert-danger">Transaction not found</div>
{% endif %}
{% endblock %}
        """)

# Create status template
status_template_path = templates_dir / "status.html"
if not status_template_path.exists():
    with open(status_template_path, "w") as f:
        f.write("""
{% extends "base.html" %}

{% block title %}System Status{% endblock %}

{% block content %}
<h1>System Status</h1>

<div class="row mb-4">
    <div class="col-md-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">API Status</h5>
                <p class="card-text {% if system_status.api_ok %}text-success{% else %}text-danger{% endif %}">
                    {{ 'Online' if system_status.api_ok else 'Offline' }}
                </p>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Blockchain Connection</h5>
                <p class="card-text {% if system_status.blockchain_ok %}text-success{% else %}text-danger{% endif %}">
                    {{ 'Connected' if system_status.blockchain_ok else 'Disconnected' }}
                </p>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Monitor Service</h5>
                <p class="card-text {% if system_status.monitor_ok %}text-success{% else %}text-danger{% endif %}">
                    {{ 'Running' if system_status.monitor_ok else 'Stopped' }}
                </p>
            </div>
        </div>
    </div>
</div>

<h2 class="mt-4">Environment Configuration</h2>
<div class="table-responsive">
    <table class="table table-striped">
        <thead>
            <tr>
                <th>Variable</th>
                <th>Value</th>
            </tr>
        </thead>
        <tbody>
            {% for key, value in env_vars.items() %}
            <tr>
                <td>{{ key }}</td>
                <td>{{ value }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<h2 class="mt-4">System Information</h2>
<div class="card">
    <div class="card-body">
        <p><strong>Database Path:</strong> {{ system_info.db_path }}</p>
        <p><strong>Transaction Count:</strong> {{ system_info.tx_count }}</p>
        <p><strong>System Time:</strong> {{ system_info.current_time }}</p>
        <p><strong>Python Version:</strong> {{ system_info.python_version }}</p>
    </div>
</div>

<div class="mt-4">
    <a href="/status/refresh" class="btn btn-primary">Refresh Status</a>
</div>
{% endblock %}
        """)

# Monitor DB Path
MONITOR_DB_PATH = os.getenv("SVDB_MONITOR_DB", "./svdb_monitor.db")

# Helper function to get database connection
def get_db_connection():
    """Get a connection to the monitor database"""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(MONITOR_DB_PATH)), exist_ok=True)
        conn = sqlite3.connect(MONITOR_DB_PATH)
        conn.row_factory = sqlite3.Row
        
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
        
        return conn
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

# Format timestamps
def format_timestamp(timestamp):
    """Format a Unix timestamp as a human-readable date"""
    if not timestamp:
        return "N/A"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

# Home page - transaction list
@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    status: str = "all", 
    search: str = "",
    db: sqlite3.Connection = Depends(get_db_connection)
):
    # Build query based on filters
    query = "SELECT * FROM transactions"
    params = []
    
    where_clauses = []
    if status != "all":
        where_clauses.append("status = ?")
        params.append(status)
    
    if search:
        where_clauses.append("(file_hash LIKE ? OR tx_hash LIKE ?)")
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    
    query += " ORDER BY timestamp DESC"
    
    # Get transactions
    cursor = db.execute(query, params)
    transactions = []
    
    for tx in cursor.fetchall():
        tx_dict = dict(tx)
        tx_dict["timestamp_formatted"] = format_timestamp(tx_dict["timestamp"])
        tx_dict["last_checked_formatted"] = format_timestamp(tx_dict["last_checked"])
        transactions.append(tx_dict)
    
    # Calculate statistics
    stats = {
        "total": len(transactions),
        "confirmed": sum(1 for tx in transactions if tx["status"] == "confirmed"),
        "pending": sum(1 for tx in transactions if tx["status"] == "pending"),
        "failed": sum(1 for tx in transactions if tx["status"] in ["failed", "error"])
    }
    
    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request, 
            "transactions": transactions,
            "stats": stats,
            "filter_status": status,
            "search_query": search
        }
    )

# Transaction detail page
@app.get("/transaction/{file_hash}", response_class=HTMLResponse)
async def transaction_detail(
    request: Request, 
    file_hash: str,
    db: sqlite3.Connection = Depends(get_db_connection)
):
    # Get transaction from database
    cursor = db.execute("SELECT * FROM transactions WHERE file_hash = ?", (file_hash,))
    tx = cursor.fetchone()
    
    if not tx:
        return templates.TemplateResponse(
            "transaction_detail.html", 
            {"request": request, "tx": None}
        )
    
    # Format transaction data
    tx_dict = dict(tx)
    tx_dict["timestamp_formatted"] = format_timestamp(tx_dict["timestamp"])
    tx_dict["last_checked_formatted"] = format_timestamp(tx_dict["last_checked"])
    
    # Parse metadata
    metadata = None
    metadata_json = ""
    if tx_dict.get("metadata"):
        try:
            metadata = json.loads(tx_dict["metadata"])
            metadata_json = json.dumps(metadata, indent=2)
        except json.JSONDecodeError:
            metadata_json = tx_dict["metadata"]
    
    # Get blockchain status if we have a tx_hash
    blockchain_status = None
    blockchain_status_json = ""
    
    if tx_dict.get("tx_hash"):
        try:
            async with BlockchainBridge() as bridge:
                blockchain_status = await bridge.check_confirmation_status(tx_dict["tx_hash"])
                blockchain_status_json = json.dumps(blockchain_status, indent=2)
        except Exception as e:
            blockchain_status_json = json.dumps({"error": str(e)}, indent=2)
    
    return templates.TemplateResponse(
        "transaction_detail.html", 
        {
            "request": request, 
            "tx": tx_dict,
            "metadata": metadata,
            "metadata_json": metadata_json,
            "blockchain_status": blockchain_status,
            "blockchain_status_json": blockchain_status_json
        }
    )

# Retry transaction
@app.get("/retry/{file_hash}", response_class=HTMLResponse)
async def retry_transaction(
    request: Request, 
    file_hash: str,
    db: sqlite3.Connection = Depends(get_db_connection)
):
    # Get transaction from database
    cursor = db.execute("SELECT * FROM transactions WHERE file_hash = ?", (file_hash,))
    tx = cursor.fetchone()
    
    if not tx:
        return templates.TemplateResponse(
            "transaction_detail.html", 
            {"request": request, "tx": None}
        )
    
    tx_dict = dict(tx)
    
    # Get metadata
    metadata = {}
    if tx_dict.get("metadata"):
        try:
            metadata = json.loads(tx_dict["metadata"])
        except json.JSONDecodeError:
            pass
    
    # Submit new transaction
    try:
        async with BlockchainBridge() as bridge:
            new_tx_hash = await bridge.submit_transaction(file_hash, metadata)
            
            # Update database
            if new_tx_hash:
                db.execute(
                    "UPDATE transactions SET tx_hash = ?, status = 'pending', retry_count = retry_count + 1, last_checked = ? WHERE file_hash = ?",
                    (new_tx_hash, int(datetime.now().timestamp()), file_hash)
                )
                db.commit()
    except Exception as e:
        print(f"Error retrying transaction: {e}")
    
    # Redirect to transaction detail page
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="0; url=/transaction/{file_hash}" />
    </head>
    <body>
        <p>Redirecting...</p>
    </body>
    </html>
    """)

# Refresh transaction status
@app.get("/refresh/{file_hash}", response_class=HTMLResponse)
async def refresh_transaction(
    request: Request, 
    file_hash: str,
    db: sqlite3.Connection = Depends(get_db_connection)
):
    # Get transaction from database
    cursor = db.execute("SELECT * FROM transactions WHERE file_hash = ?", (file_hash,))
    tx = cursor.fetchone()
    
    if not tx:
        return templates.TemplateResponse(
            "transaction_detail.html", 
            {"request": request, "tx": None}
        )
    
    tx_dict = dict(tx)
    
    # Check status if we have a tx_hash
    if tx_dict.get("tx_hash"):
        try:
            async with BlockchainBridge() as bridge:
                status = await bridge.check_confirmation_status(tx_dict["tx_hash"])
                
                # Update database
                if status.get("is_confirmed"):
                    db.execute(
                        "UPDATE transactions SET status = 'confirmed', block_hash = ?, last_checked = ? WHERE file_hash = ?",
                        (status.get("block_hash"), int(datetime.now().timestamp()), file_hash)
                    )
                else:
                    db.execute(
                        "UPDATE transactions SET last_checked = ? WHERE file_hash = ?",
                        (int(datetime.now().timestamp()), file_hash)
                    )
                db.commit()
        except Exception as e:
            print(f"Error refreshing transaction: {e}")
    
    # Redirect to transaction detail page
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="0; url=/transaction/{file_hash}" />
    </head>
    <body>
        <p>Redirecting...</p>
    </body>
    </html>
    """)

# System status page
@app.get("/status", response_class=HTMLResponse)
async def system_status(request: Request):
    system_status = {
        "api_ok": False,
        "blockchain_ok": False,
        "monitor_ok": False
    }
    
    # Check blockchain connection
    try:
        async with BlockchainBridge() as bridge:
            await bridge.get_transaction_status("test")
            system_status["blockchain_ok"] = True
    except Exception:
        pass
    
    # Check if monitor process is running (simplified check)
    monitor_process = os.popen("ps aux | grep monitor.py | grep -v grep").read()
    system_status["monitor_ok"] = bool(monitor_process)
    
    # Check API (simplified)
    try:
        import httpx
        response = await httpx.AsyncClient().get("http://localhost:8000/health", timeout=2.0)
        system_status["api_ok"] = response.status_code == 200
    except Exception:
        pass
    
    # Get environment variables (filtered)
    env_vars = {
        "SVDB_DB_PATH": os.getenv("SVDB_DB_PATH", "Not set"),
        "SVDB_MONITOR_DB": os.getenv("SVDB_MONITOR_DB", "Not set"),
        "SVDB_MONITOR_INTERVAL": os.getenv("SVDB_MONITOR_INTERVAL", "Not set"),
        "SVDB_MAX_RETRIES": os.getenv("SVDB_MAX_RETRIES", "Not set"),
        "ALERT_EMAIL_ENABLED": os.getenv("ALERT_EMAIL_ENABLED", "Not set")
    }
    
    # System info
    import sys
    import platform
    
    try:
        db = get_db_connection()
        cursor = db.execute("SELECT COUNT(*) as count FROM transactions")
        tx_count = cursor.fetchone()["count"]
        db.close()
    except Exception:
        tx_count = "Error"
    
    system_info = {
        "db_path": MONITOR_DB_PATH,
        "tx_count": tx_count,
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "python_version": f"{platform.python_implementation()} {sys.version.split()[0]}"
    }
    
    return templates.TemplateResponse(
        "status.html", 
        {
            "request": request, 
            "system_status": system_status,
            "env_vars": env_vars,
            "system_info": system_info
        }
    )

# Retry all failed transactions
@app.get("/retry", response_class=HTMLResponse)
async def retry_all(request: Request):
    db = get_db_connection()
    
    # Get all failed/error transactions
    cursor = db.execute(
        "SELECT * FROM transactions WHERE status IN ('failed', 'error') ORDER BY timestamp ASC"
    )
    failed_txs = cursor.fetchall()
    
    # Count of retried transactions
    retried_count = 0
    
    # Retry each transaction
    for tx in failed_txs:
        tx_dict = dict(tx)
        file_hash = tx_dict["file_hash"]
        
        # Get metadata
        metadata = {}
        if tx_dict.get("metadata"):
            try:
                metadata = json.loads(tx_dict["metadata"])
            except json.JSONDecodeError:
                pass
        
        # Submit new transaction
        try:
            async with BlockchainBridge() as bridge:
                new_tx_hash = await bridge.submit_transaction(file_hash, metadata)
                
                # Update database
                if new_tx_hash:
                    db.execute(
                        "UPDATE transactions SET tx_hash = ?, status = 'pending', retry_count = retry_count + 1, last_checked = ? WHERE file_hash = ?",
                        (new_tx_hash, int(datetime.now().timestamp()), file_hash)
                    )
                    retried_count += 1
        except Exception as e:
            print(f"Error retrying transaction {file_hash}: {e}")
    
    db.commit()
    db.close()
    
    # Redirect to dashboard with message
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="3; url=/" />
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; text-align: center; }}
            .message {{ margin: 20px; padding: 20px; background-color: #e8f7e8; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="message">
            <h2>Retry Complete</h2>
            <p>Retried {retried_count} out of {len(failed_txs)} failed transactions.</p>
            <p>Redirecting to dashboard in 3 seconds...</p>
            <p><a href="/">Click here if not redirected</a></p>
        </div>
    </body>
    </html>
    """)

# Main function to run the dashboard
def main():
    """Run the dashboard"""
    import uvicorn
    dashboard_port = int(os.getenv("SVDB_DASHBOARD_PORT", "8080"))
    uvicorn.run("dashboard:app", host="0.0.0.0", port=dashboard_port, reload=True)

if __name__ == "__main__":
    main() 