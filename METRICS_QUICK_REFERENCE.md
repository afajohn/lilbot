# Metrics System Quick Reference

## Quick Start

```bash
# Run audit (metrics collected automatically)
python run_audit.py --tab "Your Tab"

# Generate dashboard
python generate_report.py

# View dashboard
open dashboard.html  # Mac
start dashboard.html  # Windows
xdg-open dashboard.html  # Linux
```

## Key Files

| File | Purpose |
|------|---------|
| `metrics.json` | JSON metrics data (auto-generated) |
| `metrics.prom` | Prometheus format (auto-generated) |
| `dashboard.html` | Interactive dashboard (generated on demand) |
| `tools/metrics/metrics_collector.py` | Metrics collection engine |
| `generate_report.py` | Dashboard generator |

## Metrics Summary

### Collected Metrics

- ✅ **Success/Failure Rates** - % of successful vs failed URL analyses
- ⏱️ **Processing Time** - Average seconds per URL
- 💾 **Cache Hit Ratio** - % of results served from cache
- 🔌 **API Calls** - Count of Sheets and Cypress API calls
- 📊 **Failure Reasons** - Categorized failure counts
- 🚨 **Alert Status** - Active when failure rate >20%

### Prometheus Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `psi_audit_uptime_seconds` | Gauge | Uptime since start |
| `psi_audit_urls_total` | Counter | URLs by status |
| `psi_audit_success_rate` | Gauge | Success % |
| `psi_audit_failure_rate` | Gauge | Failure % |
| `psi_audit_cache_operations` | Counter | Cache hits/misses |
| `psi_audit_cache_hit_ratio` | Gauge | Cache hit % |
| `psi_audit_api_calls_total` | Counter | API calls by service |
| `psi_audit_processing_time_seconds` | Gauge | Avg processing time |
| `psi_audit_alert_active` | Gauge | Alert status (0/1) |

## Common Commands

### Generate Dashboard

```bash
# Default (uses current metrics)
python generate_report.py

# From specific metrics file
python generate_report.py --input metrics.json

# Custom output location
python generate_report.py --output reports/dashboard.html

# Export both formats
python generate_report.py --export-json data.json --export-prometheus data.prom
```

### View Metrics

```bash
# View JSON metrics
cat metrics.json | python -m json.tool

# View Prometheus metrics
cat metrics.prom

# View recent metrics summary
python -c "import json; m=json.load(open('metrics.json')); print(f\"Success: {m['success_rate_percent']:.1f}%\")"
```

## Alert Thresholds

| Alert | Threshold | Action |
|-------|-----------|--------|
| High Failure Rate | >20% | Appears in dashboard, logged as WARNING |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No dashboard | Install plotly: `pip install plotly` |
| No metrics files | Run an audit first |
| Alert not showing | Need ≥10 analyzed URLs |
| Dashboard won't open | Check file exists, try different browser |

## Performance Targets

| Metric | Target | Good | Warning |
|--------|--------|------|---------|
| Success Rate | 100% | >95% | <90% |
| Failure Rate | 0% | <5% | >10% |
| Cache Hit Ratio | 100% | >70% | <50% |
| Avg Processing Time | <200s | <400s | >500s |

## Integration Examples

### Check Failure Rate in Script

```bash
failure_rate=$(python -c "import json; print(json.load(open('metrics.json'))['failure_rate_percent'])")
if (( $(echo "$failure_rate > 20" | bc -l) )); then
    echo "❌ Too many failures!"
    exit 1
fi
```

### Python Integration

```python
from tools.metrics.metrics_collector import get_metrics_collector

collector = get_metrics_collector()
metrics = collector.get_metrics()

if metrics['alert_triggered']:
    print(f"⚠️ Alert: {metrics['failure_rate_percent']:.1f}% failure rate")
```

## Dashboard Features

### Metric Cards
- 📊 Total URLs, Success Rate, Failure Rate
- 💾 Cache Hit Ratio
- ⏱️ Avg Processing Time
- 🔌 API Calls

### Charts
1. URL Processing Status (Pie)
2. Success vs Failure Rate (Bar)
3. Cache Performance (Pie)
4. API Usage (Bar)
5. Processing Time (Gauge)
6. Failure Reasons (Bar)

### Alert Banner
- Appears when failure rate >20%
- Shows current rate and threshold
- Highlighted in red

## Files to Ignore

Already in `.gitignore`:
- `metrics.json`
- `metrics.prom`
- `dashboard.html`

## Next Steps

1. Run an audit to collect metrics
2. Generate dashboard: `python generate_report.py`
3. Review metrics and identify issues
4. Optimize based on findings
5. Set up automated monitoring

For detailed information, see `METRICS_GUIDE.md`.
