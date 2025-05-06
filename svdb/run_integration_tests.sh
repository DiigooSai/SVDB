#!/bin/bash
# SVDB Integration Test Runner

# Create data directories
mkdir -p data/data data/transactions

# Set environment variables for testing
export SVDB_DB_PATH="./data"
export SVDB_MONITOR_DB="./data/svdb_monitor.db"
export DEBUG="true"
export API_PORT="8000"

# Start the API server in background
echo "Starting API server..."
cd api
python3 app.py &
API_PID=$!

# Wait for API to start
echo "Waiting for API server to start..."
sleep 5

# Run the integration tests
echo "Running integration tests..."
cd ../tests
python3 integration_test.py

# Capture test result
TEST_RESULT=$?

# Kill the API server
echo "Stopping API server..."
kill $API_PID

# Return the test result
exit $TEST_RESULT 