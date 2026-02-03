# Metrics and Monitoring Guide

## Overview

The PageSpeed Insights audit tool includes a comprehensive monitoring and metrics system that tracks:

- **Success/Failure Rates**: Monitor audit success and failure percentages
- **Processing Time**: Track average time per URL analysis
- **API Quota Usage**: Monitor Google Sheets API and PageSpeed Insights API calls
- **Cache Performance**: Track cache hit ratio and efficiency
- **Failure Reasons**: Categorize and count different types of failures
- **Alerting**: Automatic alerts when failure rate exceeds 20%

## Architecture

### Components

1. **MetricsCollector** (`tools/metrics/metrics_collector.py`)
   - Thread-safe metrics collection
   - Real-time metric aggregation
   - Prometheus-compatible export format
   - JSON export for dashboards

2. **Dashboard Generator** (`generate_report.py`)
   - HTML dashboard with interactive charts
   - Plotly-based visualizations
   - Automatic alert highlighting
   - Comprehensive metric cards

3. **Integration Points**
   - `run_audit.py`: Main audit orchestration
   - `cypress_runner.py`: Cache and API tracking
   - `sheets_client.py`: API call tracking

## Metrics Collected

### URL Processing Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `psi_audit_urls_total` | Counter | Total URLs processed (by status) |
| `psi_audit_success_rate` | Gauge | Success rate percentage |
| `psi_audit_failure_rate` | Gauge | Failure rate percentage |

### Cache Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `psi_audit_cache_operations` | Counter | Cache hits and misses |
| `psi_audit_cache_hit_ratio` | Gauge | Cache hit ratio percentage |

### API Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `psi_audit_api_calls_total` | Counter | Total API calls (by service) |

### Performance Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `psi_audit_processing_time_seconds` | Gauge | Average processing time per URL |
| `psi_audit_uptime_seconds` | Gauge | Time since metrics collection started |

### Alert Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `psi_audit_alert_active` | Gauge | Whether failure rate alert is active (1=yes, 0=no) |
| `psi_audit_failures_by_reason` | Counter | Failure counts by reason |

## Usage

### Running an Audit with Metrics

Metrics are automatically collected when running audits:

```bash
python run_audit.py --tab "Your Tab Name"
```

At the end of the audit, metrics are automatically saved to:
- `metrics.json` - JSON format for dashboard generation
- `metrics.prom` - Prometheus text format for monitoring systems

### Generating the Dashboard

Generate an interactive HTML dashboard:

```bash
# Generate dashboard from current metrics
python generate_report.py

# Generate from a specific metrics file
python generate_report.py --input metrics.json --output my_dashboard.html

# Export Prometheus metrics
python generate_report.py --export-prometheus metrics.prom

# Export JSON metrics
python generate_report.py --export-json metrics.json
```

### Command-Line Options

```bash
python generate_report.py [OPTIONS]

Options:
  --input PATH              Path to JSON metrics file (optional)
  --output PATH             Path to output HTML file (default: dashboard.html)
  --export-prometheus PATH  Export Prometheus metrics to file
  --export-json PATH        Export JSON metrics to file
```

## Dashboard Features

The HTML dashboard includes:

### Metric Cards
- Total URLs processed
- Success rate (with color coding)
- Failure rate (with alert threshold)
- Cache hit ratio
- Average processing time
- API call counts

### Interactive Charts
1. **URL Processing Status** (Pie Chart)
   - Success, Failed, Skipped breakdown

2. **Success vs Failure Rate** (Bar Chart)
   - Visual comparison of rates

3. **Cache Performance** (Pie Chart)
   - Cache hits vs misses

4. **API Usage** (Bar Chart)
   - Sheets API vs Cypress API calls

5. **Processing Time** (Gauge)
   - Average time per URL with thresholds

6. **Failure Reasons** (Bar Chart)
   - Categorized failure counts

### Alert Banner

When the failure rate exceeds 20%, a prominent alert banner appears at the top of the dashboard showing:
- Current failure rate
- Number of failed URLs
- Number of analyzed URLs

## Alerting System

### Automatic Alerts

The system automatically triggers alerts when:
- Failure rate exceeds 20% (after at least 10 URLs analyzed)
- Alert is logged with WARNING level
- Alert appears in dashboard
- `psi_audit_alert_active` metric is set to 1

### Alert Content

Alerts include:
- Current failure rate percentage
- Threshold percentage (20%)
- Count of failed URLs
- Count of successful URLs
- Alert type identifier

### Alert Logging

Alerts are logged with structured data:

```python
logger.warning(
    "ALERT: Failure rate exceeded threshold! Current rate: 25.0% (threshold: 20.0%)",
    extra={
        'alert_type': 'high_failure_rate',
        'failure_rate': 0.25,
        'threshold': 0.20,
        'failed_count': 25,
        'successful_count': 75
    }
)
```

## Prometheus Integration

### Metrics Format

Metrics are exported in Prometheus text format:

```
# HELP psi_audit_uptime_seconds Time since metrics collection started
# TYPE psi_audit_uptime_seconds gauge
psi_audit_uptime_seconds 1234.56

# HELP psi_audit_urls_total Total number of URLs processed
# TYPE psi_audit_urls_total counter
psi_audit_urls_total{status="total"} 100
psi_audit_urls_total{status="success"} 85
psi_audit_urls_total{status="failed"} 10
psi_audit_urls_total{status="skipped"} 5

# HELP psi_audit_cache_hit_ratio Cache hit ratio percentage
# TYPE psi_audit_cache_hit_ratio gauge
psi_audit_cache_hit_ratio 75.00
```

### Scraping Configuration

To scrape metrics with Prometheus, configure your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'psi_audit'
    static_configs:
      - targets: ['localhost:9090']
    file_sd_configs:
      - files:
        - '/path/to/metrics.prom'
        refresh_interval: 30s
```

### Grafana Integration

Import the metrics into Grafana:

1. Add Prometheus as a data source
2. Create dashboards using PromQL queries:

```promql
# Success rate over time
psi_audit_success_rate

# Cache hit ratio
psi_audit_cache_hit_ratio

# API call rate
rate(psi_audit_api_calls_total[5m])

# Alert status
psi_audit_alert_active
```

## JSON Metrics Schema

The JSON metrics file contains:

```json
{
  "uptime_seconds": 1234.56,
  "total_urls": 100,
  "successful_urls": 85,
  "failed_urls": 10,
  "skipped_urls": 5,
  "analyzed_urls": 95,
  "success_rate_percent": 89.47,
  "failure_rate_percent": 10.53,
  "cache_hits": 60,
  "cache_misses": 35,
  "cache_hit_ratio_percent": 63.16,
  "api_calls_sheets": 150,
  "api_calls_cypress": 35,
  "total_api_calls": 185,
  "avg_processing_time_seconds": 45.67,
  "failure_reasons": {
    "timeout": 5,
    "cypress": 3,
    "permanent": 2
  },
  "alert_triggered": false
}
```

## Best Practices

### Monitoring

1. **Regular Dashboard Reviews**
   - Generate dashboard after each audit
   - Review failure reasons
   - Monitor cache efficiency

2. **Performance Tracking**
   - Track average processing time trends
   - Optimize when times increase
   - Identify bottlenecks

3. **API Quota Management**
   - Monitor API call counts
   - Stay within quota limits
   - Use cache to reduce API calls

### Alerting

1. **Alert Response**
   - Investigate when failure rate exceeds 20%
   - Check recent error logs
   - Review failure reasons in dashboard

2. **Threshold Adjustment**
   - Modify `_alert_threshold` in `MetricsCollector.__init__()` if needed
   - Default is 0.20 (20%)

### Performance Optimization

1. **Cache Optimization**
   - Monitor cache hit ratio
   - Aim for >70% cache hit ratio
   - Increase cache TTL if appropriate

2. **Concurrency Tuning**
   - Monitor processing time with different concurrency levels
   - Balance speed vs system resources

## Troubleshooting

### No Dashboard Generated

```bash
# Check if plotly is installed
pip install plotly

# Verify metrics.json exists
ls -l metrics.json

# Generate dashboard manually
python generate_report.py --input metrics.json
```

### Missing Metrics

```bash
# Ensure audit completed
# Check logs for errors
cat logs/audit_*.log

# Verify metrics files
ls -l metrics.json metrics.prom
```

### Alert Not Triggering

- Ensure at least 10 URLs have been analyzed
- Check failure rate calculation
- Review logs for alert messages
- Verify threshold (20% default)

### Dashboard Not Opening

```bash
# Check file was created
ls -l dashboard.html

# Open manually in browser
# Windows
start dashboard.html

# Mac
open dashboard.html

# Linux
xdg-open dashboard.html
```

## Advanced Usage

### Custom Metrics Export

```python
from tools.metrics.metrics_collector import get_metrics_collector

collector = get_metrics_collector()
metrics = collector.get_metrics()

# Custom processing
for reason, count in metrics['failure_reasons'].items():
    print(f"{reason}: {count}")

# Export to custom format
import json
with open('custom_metrics.json', 'w') as f:
    json.dump(metrics, f, indent=2)
```

### Programmatic Access

```python
from tools.metrics.metrics_collector import get_metrics_collector

collector = get_metrics_collector()

# Get current metrics
metrics = collector.get_metrics()
print(f"Success rate: {metrics['success_rate_percent']:.1f}%")

# Check if alert is active
if metrics['alert_triggered']:
    print("⚠️ Alert: High failure rate!")

# Get recent results
recent = collector.get_recent_results(limit=10)
for result in recent:
    print(f"{result['timestamp']}: {result['status']}")
```

### Resetting Metrics

```python
from tools.metrics.metrics_collector import reset_metrics_collector

# Reset all metrics (e.g., between runs)
reset_metrics_collector()
```

## Integration Examples

### CI/CD Pipeline

```bash
#!/bin/bash
# run_audit_with_metrics.sh

# Run audit
python run_audit.py --tab "Production URLs"

# Generate dashboard
python generate_report.py

# Check failure rate
failure_rate=$(python -c "import json; print(json.load(open('metrics.json'))['failure_rate_percent'])")

if (( $(echo "$failure_rate > 20" | bc -l) )); then
    echo "❌ Failure rate too high: $failure_rate%"
    exit 1
fi

echo "✅ Audit passed: $failure_rate% failure rate"
```

### Scheduled Monitoring

```python
# scheduled_audit.py
import subprocess
import sys
from tools.metrics.metrics_collector import get_metrics_collector

# Run audit
result = subprocess.run(['python', 'run_audit.py', '--tab', 'Production'])

if result.returncode != 0:
    sys.exit(1)

# Check metrics
collector = get_metrics_collector()
metrics = collector.get_metrics()

# Generate report
subprocess.run(['python', 'generate_report.py'])

# Send alert if needed
if metrics['alert_triggered']:
    send_alert(metrics)  # Your custom alert function
```

## Future Enhancements

Potential future improvements:

1. **Real-time Monitoring**
   - WebSocket-based live dashboard
   - Streaming metrics updates

2. **Historical Tracking**
   - Time-series database integration
   - Trend analysis
   - Comparative reports

3. **Advanced Alerting**
   - Email notifications
   - Slack/Teams integration
   - Custom alert rules

4. **Machine Learning**
   - Anomaly detection
   - Predictive failure analysis
   - Performance forecasting

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review log files in `logs/`
3. Verify all dependencies are installed
4. Check the AGENTS.md file for additional context
