#!/usr/bin/env python3
"""
SVDB Load Test

This script performs load testing on the SVDB API:
1. Concurrent file uploads of varying sizes
2. Measurement of throughput and latency
3. Stress testing with high concurrency
"""
import os
import sys
import time
import asyncio
import argparse
import logging
import tempfile
import random
import statistics
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("svdb.load_test")

# Default API URL
API_URL = "http://localhost:8000"

class LoadTest:
    """Load test runner for SVDB"""
    
    def __init__(self, api_url=API_URL):
        """Initialize the load test"""
        self.api_url = api_url
        self.results = {
            "small_files": [],  # 10KB files
            "medium_files": [], # 1MB files
            "large_files": [],  # 10MB files
            "errors": 0
        }
    
    async def upload_file(self, file_path, file_category):
        """Upload a file and measure the time taken"""
        import aiohttp
        
        start_time = time.time()
        file_size = os.path.getsize(file_path)
        
        try:
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('file', f, filename=os.path.basename(file_path))
                    
                    async with session.post(f"{self.api_url}/store", data=data) as response:
                        if response.status == 200:
                            resp_json = await response.json()
                            file_hash = resp_json.get("hash")
                            
                            end_time = time.time()
                            duration = end_time - start_time
                            
                            # Calculate throughput (MB/s)
                            throughput = (file_size / 1024 / 1024) / duration if duration > 0 else 0
                            
                            # Record results
                            self.results[file_category].append({
                                "file_size": file_size,
                                "duration": duration,
                                "throughput": throughput,
                                "hash": file_hash
                            })
                            
                            return file_hash
                        else:
                            logger.error(f"Error uploading file: {response.status}")
                            self.results["errors"] += 1
                            return None
        except Exception as e:
            logger.error(f"Exception during upload: {e}")
            self.results["errors"] += 1
            return None
    
    async def run_concurrency_test(self, concurrency, file_sizes):
        """Run a concurrency test with the specified number of concurrent uploads"""
        logger.info(f"Running concurrency test with {concurrency} concurrent uploads")
        
        # Create temporary files of various sizes
        files = []
        for size_category, size_bytes in file_sizes.items():
            for i in range(concurrency):
                temp_file = tempfile.NamedTemporaryFile(delete=False)
                # Use random data to prevent compression effects
                temp_file.write(os.urandom(size_bytes))
                temp_file.close()
                files.append((temp_file.name, size_category))
        
        # Run concurrent uploads
        tasks = []
        for file_path, size_category in files:
            tasks.append(self.upload_file(file_path, size_category))
        
        # Wait for all uploads to complete
        await asyncio.gather(*tasks)
        
        # Clean up temporary files
        for file_path, _ in files:
            try:
                os.unlink(file_path)
            except:
                pass
    
    def print_results(self):
        """Print the test results"""
        print("\n==== SVDB Load Test Results ====")
        print(f"API URL: {self.api_url}")
        print(f"Time: {datetime.now()}")
        print(f"Total errors: {self.results['errors']}")
        
        for category in ["small_files", "medium_files", "large_files"]:
            if not self.results[category]:
                continue
                
            durations = [r["duration"] for r in self.results[category]]
            throughputs = [r["throughput"] for r in self.results[category]]
            
            print(f"\n=== {category.replace('_', ' ').title()} ===")
            print(f"Count: {len(self.results[category])}")
            print(f"Average duration: {statistics.mean(durations):.3f}s")
            if len(durations) > 1:
                print(f"Duration std dev: {statistics.stdev(durations):.3f}s")
            print(f"Min duration: {min(durations):.3f}s")
            print(f"Max duration: {max(durations):.3f}s")
            print(f"Average throughput: {statistics.mean(throughputs):.2f} MB/s")
    
    def save_results(self, filename):
        """Save the results to a JSON file"""
        import json
        
        with open(filename, 'w') as f:
            json.dump({
                "api_url": self.api_url,
                "timestamp": datetime.now().isoformat(),
                "results": self.results
            }, f, indent=2)
        
        logger.info(f"Results saved to {filename}")
        
async def health_check(api_url):
    """Check if the API server is running"""
    import aiohttp
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/health") as response:
                if response.status == 200:
                    return True
                else:
                    logger.error(f"API server returned status {response.status}")
                    return False
    except Exception as e:
        logger.error(f"API server health check failed: {e}")
        return False

async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="SVDB Load Test")
    parser.add_argument("--url", default=API_URL, help=f"API URL (default: {API_URL})")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent uploads (default: 10)")
    parser.add_argument("--output", help="Output file for results (JSON)")
    args = parser.parse_args()
    
    # Check if API server is running
    api_running = await health_check(args.url)
    if not api_running:
        logger.error("API server is not running. Please start the API server first.")
        return 1
    
    # Define file sizes for tests
    file_sizes = {
        "small_files": 10 * 1024,  # 10KB
        "medium_files": 1 * 1024 * 1024,  # 1MB
        "large_files": 10 * 1024 * 1024,  # 10MB
    }
    
    # Run the load test
    load_test = LoadTest(api_url=args.url)
    
    logger.info("Starting load test...")
    start_time = time.time()
    
    await load_test.run_concurrency_test(args.concurrency, file_sizes)
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    logger.info(f"Load test completed in {total_duration:.2f} seconds")
    
    # Print and save results
    load_test.print_results()
    
    if args.output:
        load_test.save_results(args.output)
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Load test interrupted by user")
        sys.exit(1) 