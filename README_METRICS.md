# Metrics and Monitoring System

The PageSpeed Insights Audit Tool includes a comprehensive metrics and monitoring system that automatically tracks audit performance, cache efficiency, API usage, and failure rates.

## Quick Start

### 1. Run an Audit

Metrics are automatically collected:

```bash
python run_audit.py --tab "Your Tab Name"
```

At the end of the audit, you'll see:
```
Metrics saved to metrics.json and metrics.prom
Generate HTML dashboard with: python generate_report.py
```

### 2. Generate Dashboard

Create an interactive HTML dashboard:

```bash
python generate_report.py
```

This generates `dashboard.html` with:
- Interactive charts (Plotly)
- Real-time metrics
- Alert notifications
- Failure analysis

### 3. View Dashboard

Open the dashboard in your browser:

```bash
# Mac
open dashboard.html

# Windows
start dashboard.html

# Linux
xdg-open dashboard.html
```

## What's Tracked

### Key Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Success Rate** | % of URLs successfully analyzed | >95% |
| **Failure Rate** | % of URLs that failed | <5% |
| **Cache Hit Ratio** | % of results served from cache | >70% |
| **Avg Processing Time** | Seconds per URL | <200s |
| **API Calls** | Total API requests (Sheets + Cypress) | Monitor quota |

### Automatic Alerts

- ⚠️ **Alert triggered** when failure rate exceeds **20%**
- Appears in dashboard with red banner
- Logged as WARNING in audit logs
- Includes failure counts and rates

## Dashboard Features

### Metric Cards
Quick overview of key statistics:
- Total URLs processed
- Success/failure rates
- Cache performance
- API usage
- Average processing time

### Interactive Charts
1. **URL Processing Status** - Pie chart showing success/failed/skipped
2. **Success vs Failure Rate** - Bar chart comparing rates
3. **Cache Performance** - Pie chart of hits vs misses
4. **API Usage** - Bar chart of Sheets vs Cypress calls
5. **Processing Time Gauge** - Visual indicator with thresholds
6. **Failure Reasons** - Bar chart categorizing failures

## Exported Files

| File | Format | Purpose |
|------|--------|---------|
| `metrics.json` | JSON | Dashboard source data, analysis |
| `metrics.prom` | Prometheus | Monitoring system integration |
| `dashboard.html` | HTML | Interactive web dashboard |

All files are automatically added to `.gitignore`.

## Advanced Usage

### Export Specific Formats

```bash
# Export Prometheus metrics
python generate_report.py --export-prometheus my_metrics.prom

# Export JSON metrics
python generate_report.py --export-json my_metrics.json

# Use specific input file
python generate_report.py --input old_metrics.json --output report.html
```

### Prometheus Integration

The `metrics.prom` file is compatible with Prometheus monitoring:

```prometheus
# Example metrics
psi_audit_success_rate 92.50
psi_audit_failure_rate 7.50
psi_audit_cache_hit_ratio 75.00
psi_audit_processing_time_seconds 145.67
```

### Programmatic Access

```python
from tools.metrics.metrics_collector import get_metrics_collector

collector = get_metrics_collector()
metrics = collector.get_metrics()

print(f"Success rate: {metrics['success_rate_percent']:.1f}%")

if metrics['alert_triggered']:
    print("⚠️ High failure rate detected!")
```

## Interpreting Results

### Success Rate
- **>95%**: Excellent - system performing well
- **90-95%**: Good - minor issues to investigate
- **<90%**: Poor - requires immediate attention

### Cache Hit Ratio
- **>70%**: Excellent - cache is effective
- **50-70%**: Good - room for optimization
- **<50%**: Poor - check cache configuration

### Processing Time
- **<200s**: Fast - optimal performance
- **200-400s**: Normal - acceptable range
- **>400s**: Slow - may need timeout adjustment

### Failure Rate
- **<5%**: Excellent - minimal failures
- **5-20%**: Warning - investigate failure reasons
- **>20%**: Alert - immediate action required

## Troubleshooting

### Dashboard Won't Generate

```bash
# Install plotly if missing
pip install plotly

# Verify metrics file exists
ls -l metrics.json

# Generate manually
python generate_report.py --input metrics.json
```

### No Metrics After Audit

Check that:
1. Audit completed successfully
2. `metrics.json` and `metrics.prom` were created
3. No permission errors in logs

### Alert Not Showing

Alerts require:
- At least 10 URLs analyzed
- Failure rate above 20%
- Check `metrics['alert_triggered']` in JSON

## Best Practices

### Regular Monitoring
1. Review dashboard after each audit
2. Track trends over multiple runs
3. Set up automated alerting if needed

### Performance Optimization
1. Monitor cache hit ratio - aim for >70%
2. Track processing time trends
3. Review failure reasons to identify patterns

### API Quota Management
1. Monitor API call counts
2. Use cache to reduce API usage
3. Stay within Google Sheets quotas

## Documentation

For detailed information, see:
- **METRICS_GUIDE.md** - Comprehensive documentation
- **METRICS_QUICK_REFERENCE.md** - Quick command reference
- **AGENTS.md** - Technical architecture details

## Examples

### Check If Failure Rate Is Too High

```bash
#!/bin/bash
failure_rate=$(python -c "import json; print(json.load(open('metrics.json'))['failure_rate_percent'])")

if (( $(echo "$failure_rate > 20" | bc -l) )); then
    echo "❌ Failure rate too high: $failure_rate%"
    exit 1
else
    echo "✅ Acceptable failure rate: $failure_rate%"
fi
```

### Automated Reporting

```python
import subprocess
from tools.metrics.metrics_collector import get_metrics_collector

# Run audit
subprocess.run(['python', 'run_audit.py', '--tab', 'Production'])

# Generate dashboard
subprocess.run(['python', 'generate_report.py'])

# Send alert if needed
collector = get_metrics_collector()
if collector.get_metrics()['alert_triggered']:
    send_email_alert()  # Your alert function
```

## Support

If you encounter issues:
1. Check this README
2. Review METRICS_GUIDE.md
3. Check audit logs in `logs/`
4. Verify all dependencies installed

---

**Note**: Metrics collection is automatic and has minimal performance impact. The system is thread-safe and works with concurrent URL processing.
