#!/bin/bash
# SVDB Production-Ready Load Test Runner

# Create data directories
mkdir -p data/data data/transactions

# Set environment variables for testing
export SVDB_DB_PATH="./data"
export SVDB_MONITOR_DB="./data/svdb_monitor.db"
export DEBUG="false"
export API_PORT="8000"
export API_WORKERS="16"  # Increased from 4 to 16 for production testing

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "   SVDB Production Load Testing Suite     "
echo "=========================================="

# Start the API server in background
echo -e "${YELLOW}Starting API server with ${API_WORKERS} workers...${NC}"
cd api
python3 app.py &
API_PID=$!

# Wait for API to start
echo "Waiting for API server to start..."
sleep 5

# Create test result directory with timestamp
TIMESTAMP=$(date +"%Y%m%d%H%M%S")
RESULTS_DIR="../tests/load_test_results_${TIMESTAMP}"
mkdir -p ${RESULTS_DIR}

cd ../tests

# Function to run load test with specific parameters
run_test() {
    local concurrency=$1
    local duration=$2
    local test_name=$3
    local endpoint=$4
    local payload=$5
    
    echo -e "${YELLOW}Running test: ${test_name} (Concurrency: ${concurrency}, Duration: ${duration}s)${NC}"
    
    if [ -z "$payload" ]; then
        # GET request test
        python3 load_test.py --concurrency ${concurrency} --duration ${duration} \
            --endpoint ${endpoint} --output "${RESULTS_DIR}/${test_name}.json"
    else
        # POST request test
        python3 load_test.py --concurrency ${concurrency} --duration ${duration} \
            --endpoint ${endpoint} --payload "${payload}" \
            --output "${RESULTS_DIR}/${test_name}.json"
    fi
    
    # Extract key metrics
    RPS=$(cat "${RESULTS_DIR}/${test_name}.json" | grep -o '"requests_per_second": [0-9.]*' | cut -d' ' -f2)
    AVG_LATENCY=$(cat "${RESULTS_DIR}/${test_name}.json" | grep -o '"average_latency_ms": [0-9.]*' | cut -d' ' -f2)
    ERROR_RATE=$(cat "${RESULTS_DIR}/${test_name}.json" | grep -o '"error_rate": [0-9.]*' | cut -d' ' -f2)
    
    echo -e "Results:"
    echo -e "  Requests per second: ${GREEN}${RPS}${NC}"
    echo -e "  Average latency: ${GREEN}${AVG_LATENCY} ms${NC}"
    echo -e "  Error rate: ${GREEN}${ERROR_RATE}%${NC}"
    echo ""
    
    # Save to summary file
    echo "${test_name}, ${concurrency}, ${duration}, ${RPS}, ${AVG_LATENCY}, ${ERROR_RATE}" >> "${RESULTS_DIR}/summary.csv"
}

# Create summary file header
echo "Test Name, Concurrency, Duration, Requests/sec, Avg Latency (ms), Error Rate (%)" > "${RESULTS_DIR}/summary.csv"

# Test 1: Health Endpoint (Low Load)
run_test 10 30 "health_check_low" "/health" ""

# Test 2: Health Endpoint (Medium Load)
run_test 50 30 "health_check_medium" "/health" ""

# Test 3: Health Endpoint (High Load)
run_test 200 30 "health_check_high" "/health" ""

# Test 4: Verification Endpoint (Low Load)
run_test 10 30 "verify_endpoint_low" "/verify/c97195f3fca2764f95fcdadaf129c6bd0d3612d41cd464eb82d6293b4d3d9109" ""

# Test 5: Verification Endpoint (Medium Load)
run_test 50 30 "verify_endpoint_medium" "/verify/c97195f3fca2764f95fcdadaf129c6bd0d3612d41cd464eb82d6293b4d3d9109" ""

# Test 6: Verification Endpoint (High Load)
run_test 100 30 "verify_endpoint_high" "/verify/c97195f3fca2764f95fcdadaf129c6bd0d3612d41cd464eb82d6293b4d3d9109" ""

# Test 7: Store Endpoint (Low Load)
STORE_PAYLOAD='{"file_data": "SGVsbG8gV29ybGQ=", "filename": "test.txt", "content_type": "text/plain"}'
run_test 5 30 "store_endpoint_low" "/store" "${STORE_PAYLOAD}"

# Test 8: Store Endpoint (Medium Load)
run_test 20 30 "store_endpoint_medium" "/store" "${STORE_PAYLOAD}"

# Test 9: Store Endpoint (Production Load)
run_test 50 30 "store_endpoint_production" "/store" "${STORE_PAYLOAD}"

# Test 10: Mixed Workload (Production Simulation)
echo -e "${YELLOW}Running mixed workload test (simulates real production traffic)...${NC}"
python3 load_test.py --mixed-workload --concurrency 100 --duration 60 \
    --output "${RESULTS_DIR}/mixed_workload_production.json"

# Kill the API server
echo -e "${YELLOW}Stopping API server...${NC}"
kill $API_PID

# Generate HTML report
echo -e "${YELLOW}Generating test report...${NC}"
python3 generate_report.py --input-dir "${RESULTS_DIR}" --output "${RESULTS_DIR}/report.html"

echo -e "${GREEN}Load test complete.${NC}"
echo -e "Results saved to ${RESULTS_DIR}"
echo -e "Summary report: ${RESULTS_DIR}/report.html"

# Check if any test failed production requirements
FAILED_TESTS=$(grep -c ",.*,.*,.*,.*,.*,[5-9][0-9]\." "${RESULTS_DIR}/summary.csv" || true)
if [ "$FAILED_TESTS" -gt 0 ]; then
    echo -e "${RED}WARNING: $FAILED_TESTS tests had error rates above 5%.${NC}"
    echo -e "${RED}API may not be ready for production traffic.${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed production requirements.${NC}"
    exit 0
fi 