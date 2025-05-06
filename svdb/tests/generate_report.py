#!/usr/bin/env python3
"""
SVDB Load Test Report Generator
Generates HTML reports from load test results.
"""

import os
import json
import argparse
import datetime
from pathlib import Path


def load_test_results(input_dir):
    """Load all test result JSON files from the input directory."""
    results = {}
    summary = []
    
    # Check for summary.csv
    summary_file = os.path.join(input_dir, "summary.csv")
    if os.path.exists(summary_file):
        with open(summary_file, 'r') as f:
            # Skip header
            next(f)
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 6:
                    summary.append({
                        'test_name': parts[0].strip(),
                        'concurrency': int(parts[1]),
                        'duration': int(parts[2]),
                        'rps': float(parts[3]),
                        'latency': float(parts[4]),
                        'error_rate': float(parts[5])
                    })
    
    # Load individual test results
    for file in Path(input_dir).glob('*.json'):
        try:
            with open(file, 'r') as f:
                results[file.stem] = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading {file}: {e}")
    
    return results, summary


def generate_html_report(results, summary, output_file):
    """Generate an HTML report from the test results."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Start generating HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SVDB Load Test Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; color: #333; }}
            h1, h2, h3 {{ color: #2c3e50; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .card {{ background: white; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); 
                    padding: 20px; margin-bottom: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f2f2f2; }}
            tr:hover {{ background-color: #f5f5f5; }}
            .success {{ color: green; }}
            .warning {{ color: orange; }}
            .error {{ color: red; }}
            .chart-container {{ height: 400px; margin: 20px 0; }}
            
            .gauge-container {{
                display: inline-block;
                width: 200px;
                text-align: center;
                margin: 20px;
            }}
            .gauge {{ width: 100%; height: 100px; }}
            @media (max-width: 768px) {{
                th, td {{ padding: 8px 10px; }}
                .card {{ padding: 15px; }}
            }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
        <div class="container">
            <h1>SVDB Load Test Report</h1>
            <p>Generated on: {now}</p>
            
            <div class="card">
                <h2>Test Summary</h2>
                <div style="display: flex; flex-wrap: wrap; justify-content: space-around;">
                    <div class="gauge-container">
                        <h3>Avg Throughput</h3>
                        <canvas id="throughputGauge" class="gauge"></canvas>
                        <div id="throughputValue"></div>
                    </div>
                    <div class="gauge-container">
                        <h3>Avg Latency</h3>
                        <canvas id="latencyGauge" class="gauge"></canvas>
                        <div id="latencyValue"></div>
                    </div>
                    <div class="gauge-container">
                        <h3>Avg Error Rate</h3>
                        <canvas id="errorGauge" class="gauge"></canvas>
                        <div id="errorValue"></div>
                    </div>
                </div>
                
                <h3>Test Results</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Test Name</th>
                            <th>Concurrency</th>
                            <th>Duration (s)</th>
                            <th>Requests/sec</th>
                            <th>Avg Latency (ms)</th>
                            <th>Error Rate (%)</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    
    # Add rows for each test
    for test in summary:
        status_class = "success"
        status_text = "PASS"
        
        if test['error_rate'] > 5.0:
            status_class = "error"
            status_text = "FAIL"
        elif test['error_rate'] > 1.0:
            status_class = "warning"
            status_text = "WARNING"
            
        html += f"""
                        <tr>
                            <td>{test['test_name']}</td>
                            <td>{test['concurrency']}</td>
                            <td>{test['duration']}</td>
                            <td>{test['rps']:.2f}</td>
                            <td>{test['latency']:.2f}</td>
                            <td>{test['error_rate']:.2f}%</td>
                            <td class="{status_class}">{status_text}</td>
                        </tr>
        """
    
    # Continue with the HTML template
    html += """
                    </tbody>
                </table>
            </div>
            
            <div class="card">
                <h2>Performance Charts</h2>
                <div class="chart-container">
                    <canvas id="rpsChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="latencyChart"></canvas>
                </div>
                <div class="chart-container">
                    <canvas id="errorChart"></canvas>
                </div>
            </div>
            
            <div class="card">
                <h2>Recommendations</h2>
                <div id="recommendations">
                    <!-- Will be filled by JavaScript -->
                </div>
            </div>
        </div>
        
        <script>
            // Prepare data for charts
            const testData = {
    """
    
    # Add JavaScript data for the charts
    test_names_js = json.dumps([test['test_name'] for test in summary])
    rps_js = json.dumps([test['rps'] for test in summary])
    latency_js = json.dumps([test['latency'] for test in summary])
    error_rates_js = json.dumps([test['error_rate'] for test in summary])
    
    html += f"""
                testNames: {test_names_js},
                rps: {rps_js},
                latency: {latency_js},
                errorRates: {error_rates_js}
            }};
            
            // Calculate averages
            const avgRps = testData.rps.reduce((a, b) => a + b, 0) / testData.rps.length || 0;
            const avgLatency = testData.latency.reduce((a, b) => a + b, 0) / testData.latency.length || 0;
            const avgErrorRate = testData.errorRates.reduce((a, b) => a + b, 0) / testData.errorRates.length || 0;
            
            // Update gauge values
            document.getElementById('throughputValue').textContent = avgRps.toFixed(2) + ' req/s';
            document.getElementById('latencyValue').textContent = avgLatency.toFixed(2) + ' ms';
            document.getElementById('errorValue').textContent = avgErrorRate.toFixed(2) + '%';
            
            // Create gauges
            new Chart(document.getElementById('throughputGauge'), {{
                type: 'doughnut',
                data: {{
                    datasets: [{{
                        data: [avgRps, Math.max(500 - avgRps, 0)],
                        backgroundColor: [avgRps > 100 ? '#4CAF50' : '#FFA500', '#f0f0f0']
                    }}]
                }},
                options: {{ cutout: '70%', circumference: 180, rotation: 270, plugins: {{ tooltip: {{ enabled: false }}, legend: {{ display: false }} }} }}
            }});
            
            new Chart(document.getElementById('latencyGauge'), {{
                type: 'doughnut',
                data: {{
                    datasets: [{{
                        data: [avgLatency, Math.max(1000 - avgLatency, 0)],
                        backgroundColor: [avgLatency < 200 ? '#4CAF50' : avgLatency < 500 ? '#FFA500' : '#F44336', '#f0f0f0']
                    }}]
                }},
                options: {{ cutout: '70%', circumference: 180, rotation: 270, plugins: {{ tooltip: {{ enabled: false }}, legend: {{ display: false }} }} }}
            }});
            
            new Chart(document.getElementById('errorGauge'), {{
                type: 'doughnut',
                data: {{
                    datasets: [{{
                        data: [avgErrorRate, Math.max(100 - avgErrorRate, 0)],
                        backgroundColor: [avgErrorRate < 1 ? '#4CAF50' : avgErrorRate < 5 ? '#FFA500' : '#F44336', '#f0f0f0']
                    }}]
                }},
                options: {{ cutout: '70%', circumference: 180, rotation: 270, plugins: {{ tooltip: {{ enabled: false }}, legend: {{ display: false }} }} }}
            }});
            
            // Create RPS chart
            new Chart(document.getElementById('rpsChart'), {{
                type: 'bar',
                data: {{
                    labels: testData.testNames,
                    datasets: [{{
                        label: 'Requests per Second',
                        data: testData.rps,
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgba(54, 162, 235, 1)',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{ title: {{ display: true, text: 'Throughput by Test' }} }},
                    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Requests/sec' }} }} }}
                }}
            }});
            
            // Create latency chart
            new Chart(document.getElementById('latencyChart'), {{
                type: 'bar',
                data: {{
                    labels: testData.testNames,
                    datasets: [{{
                        label: 'Average Latency (ms)',
                        data: testData.latency,
                        backgroundColor: 'rgba(75, 192, 192, 0.5)',
                        borderColor: 'rgba(75, 192, 192, 1)',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{ title: {{ display: true, text: 'Latency by Test' }} }},
                    scales: {{ y: {{ beginAtZero: true, title: {{ display: true, text: 'Milliseconds' }} }} }}
                }}
            }});
            
            // Create error rate chart
            new Chart(document.getElementById('errorChart'), {{
                type: 'bar',
                data: {{
                    labels: testData.testNames,
                    datasets: [{{
                        label: 'Error Rate (%)',
                        data: testData.errorRates,
                        backgroundColor: 'rgba(255, 99, 132, 0.5)',
                        borderColor: 'rgba(255, 99, 132, 1)',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    plugins: {{ title: {{ display: true, text: 'Error Rate by Test' }} }},
                    scales: {{ 
                        y: {{ 
                            beginAtZero: true, 
                            title: {{ display: true, text: 'Error Rate (%)' }},
                            suggestedMax: 10
                        }} 
                    }}
                }}
            }});
            
            // Generate recommendations
            const recommendations = document.getElementById('recommendations');
            let recommendationHTML = '<ul>';
            
            if (avgRps < 50) {{
                recommendationHTML += '<li>The API throughput is lower than expected for production use. Consider optimizing database queries and API endpoints.</li>';
            }}
            
            if (avgLatency > 300) {{
                recommendationHTML += '<li>Average latency is high. Look into caching strategies and database query optimization.</li>';
            }}
            
            if (avgErrorRate > 1) {{
                recommendationHTML += '<li>Error rate exceeds 1%. Investigate error logs to identify and resolve issues before production deployment.</li>';
            }}
            
            const highErrorTests = testData.testNames.filter((_, i) => testData.errorRates[i] > 5);
            if (highErrorTests.length > 0) {{
                recommendationHTML += `<li>Tests with high error rates (>5%): ${highErrorTests.join(', ')}. These require immediate attention.</li>`;
            }}
            
            const highLatencyTests = testData.testNames.filter((_, i) => testData.latency[i] > 500);
            if (highLatencyTests.length > 0) {{
                recommendationHTML += `<li>Tests with high latency (>500ms): ${highLatencyTests.join(', ')}. Consider optimizing these endpoints.</li>`;
            }}
            
            if (recommendationHTML === '<ul>') {{
                recommendationHTML += '<li>All tests are performing well. The API appears ready for production traffic!</li>';
            }}
            
            recommendationHTML += '</ul>';
            recommendations.innerHTML = recommendationHTML;
        </script>
    </body>
    </html>
    """
    
    # Write the HTML to file
    with open(output_file, 'w') as f:
        f.write(html)
    
    print(f"Report generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Generate HTML report from load test results')
    parser.add_argument('--input-dir', required=True, help='Directory containing test result files')
    parser.add_argument('--output', required=True, help='Output HTML file path')
    args = parser.parse_args()
    
    results, summary = load_test_results(args.input_dir)
    generate_html_report(results, summary, args.output)


if __name__ == '__main__':
    main() 