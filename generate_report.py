#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    print("Warning: plotly not installed. Install with: pip install plotly")

from metrics.metrics_collector import get_metrics_collector


def generate_html_dashboard(metrics: Dict, output_file: str = 'dashboard.html'):
    """
    Generate an interactive HTML dashboard with charts using Plotly.
    
    Args:
        metrics: Dictionary of metrics data
        output_file: Path to output HTML file
    """
    if not PLOTLY_AVAILABLE:
        print("Error: plotly is required to generate dashboard")
        print("Install with: pip install plotly")
        sys.exit(1)
    
    fig = make_subplots(
        rows=4, cols=2,
        subplot_titles=(
            'URL Processing Status',
            'Success vs Failure Rate',
            'Cache Performance',
            'API Usage',
            'Processing Time',
            'Failure Reasons',
            'Playwright Warm/Cold Starts',
            'Playwright Performance'
        ),
        specs=[
            [{"type": "pie"}, {"type": "bar"}],
            [{"type": "pie"}, {"type": "bar"}],
            [{"type": "indicator"}, {"type": "bar"}],
            [{"type": "pie"}, {"type": "bar"}]
        ]
    )
    
    fig.add_trace(
        go.Pie(
            labels=['Success', 'Failed', 'Skipped'],
            values=[
                metrics['successful_urls'],
                metrics['failed_urls'],
                metrics['skipped_urls']
            ],
            marker=dict(colors=['#2ecc71', '#e74c3c', '#95a5a6']),
            name='URL Status'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Bar(
            x=['Success Rate', 'Failure Rate'],
            y=[metrics['success_rate_percent'], metrics['failure_rate_percent']],
            marker=dict(color=['#2ecc71', '#e74c3c']),
            text=[f"{metrics['success_rate_percent']:.1f}%", f"{metrics['failure_rate_percent']:.1f}%"],
            textposition='auto',
            name='Rates'
        ),
        row=1, col=2
    )
    
    fig.add_trace(
        go.Pie(
            labels=['Cache Hits', 'Cache Misses'],
            values=[metrics['cache_hits'], metrics['cache_misses']],
            marker=dict(colors=['#3498db', '#e67e22']),
            name='Cache'
        ),
        row=2, col=1
    )
    
    fig.add_trace(
        go.Bar(
            x=['Sheets API'],
            y=[metrics['api_calls_sheets']],
            marker=dict(color=['#9b59b6']),
            text=[metrics['api_calls_sheets']],
            textposition='auto',
            name='API Calls'
        ),
        row=2, col=2
    )
    
    fig.add_trace(
        go.Indicator(
            mode="gauge+number+delta",
            value=metrics['avg_processing_time_seconds'],
            title={'text': "Avg Processing Time (s)"},
            delta={'reference': 600},
            gauge={
                'axis': {'range': [None, 600]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 200], 'color': "lightgreen"},
                    {'range': [200, 400], 'color': "yellow"},
                    {'range': [400, 600], 'color': "orange"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 600
                }
            }
        ),
        row=3, col=1
    )
    
    if metrics['failure_reasons']:
        reasons = list(metrics['failure_reasons'].keys())
        counts = list(metrics['failure_reasons'].values())
        
        fig.add_trace(
            go.Bar(
                x=reasons,
                y=counts,
                marker=dict(color='#e74c3c'),
                text=counts,
                textposition='auto',
                name='Failures'
            ),
            row=3, col=2
        )
    
    pw_metrics = metrics.get('playwright', {})
    if pw_metrics:
        fig.add_trace(
            go.Pie(
                labels=['Warm Starts', 'Cold Starts'],
                values=[
                    pw_metrics.get('warm_starts', 0),
                    pw_metrics.get('cold_starts', 0)
                ],
                marker=dict(colors=['#2ecc71', '#3498db']),
                name='Start Type'
            ),
            row=4, col=1
        )
        
        fig.add_trace(
            go.Bar(
                x=['Page Load', 'Browser Startup', 'Avg Memory'],
                y=[
                    pw_metrics.get('avg_page_load_time_seconds', 0),
                    pw_metrics.get('avg_browser_startup_time_seconds', 0),
                    pw_metrics.get('avg_memory_usage_mb', 0) / 100
                ],
                marker=dict(color=['#9b59b6', '#1abc9c', '#e67e22']),
                text=[
                    f"{pw_metrics.get('avg_page_load_time_seconds', 0):.2f}s",
                    f"{pw_metrics.get('avg_browser_startup_time_seconds', 0):.2f}s",
                    f"{pw_metrics.get('avg_memory_usage_mb', 0):.0f}MB"
                ],
                textposition='auto',
                name='Performance'
            ),
            row=4, col=2
        )
    
    fig.update_layout(
        height=1600,
        title_text=f"PageSpeed Insights Audit Dashboard - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        showlegend=False
    )
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PSI Audit Dashboard</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .header p {{
            margin: 5px 0;
            opacity: 0.9;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-card h3 {{
            margin: 0 0 10px 0;
            color: #666;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metric-card .value {{
            font-size: 32px;
            font-weight: bold;
            color: #333;
        }}
        .metric-card .subvalue {{
            font-size: 14px;
            color: #999;
            margin-top: 5px;
        }}
        .alert {{
            background-color: #e74c3c;
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .alert h3 {{
            margin: 0 0 5px 0;
        }}
        .charts {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #999;
            font-size: 12px;
        }}
        .success {{ color: #2ecc71; }}
        .failure {{ color: #e74c3c; }}
        .warning {{ color: #f39c12; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 PageSpeed Insights Audit Dashboard</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Uptime: {metrics['uptime_seconds']:.2f} seconds ({metrics['uptime_seconds']/60:.1f} minutes)</p>
    </div>
    
    {generate_alert_html(metrics) if metrics['alert_triggered'] else ''}
    
    <div class="metrics-grid">
        <div class="metric-card">
            <h3>Total URLs</h3>
            <div class="value">{metrics['total_urls']}</div>
            <div class="subvalue">Analyzed: {metrics['analyzed_urls']}</div>
        </div>
        
        <div class="metric-card">
            <h3>Success Rate</h3>
            <div class="value success">{metrics['success_rate_percent']:.1f}%</div>
            <div class="subvalue">{metrics['successful_urls']} successful</div>
        </div>
        
        <div class="metric-card">
            <h3>Failure Rate</h3>
            <div class="value {'failure' if metrics['failure_rate_percent'] > 20 else 'warning' if metrics['failure_rate_percent'] > 10 else ''}">{metrics['failure_rate_percent']:.1f}%</div>
            <div class="subvalue">{metrics['failed_urls']} failed</div>
        </div>
        
        <div class="metric-card">
            <h3>Cache Hit Ratio</h3>
            <div class="value">{metrics['cache_hit_ratio_percent']:.1f}%</div>
            <div class="subvalue">{metrics['cache_hits']} hits / {metrics['cache_misses']} misses</div>
        </div>
        
        <div class="metric-card">
            <h3>Avg Processing Time</h3>
            <div class="value">{metrics['avg_processing_time_seconds']:.1f}s</div>
            <div class="subvalue">Per URL</div>
        </div>
        
        <div class="metric-card">
            <h3>API Calls</h3>
            <div class="value">{metrics['total_api_calls']}</div>
            <div class="subvalue">Sheets: {metrics['api_calls_sheets']}</div>
        </div>
    </div>
    
    {generate_playwright_metrics_html(metrics) if metrics.get('playwright') else ''}
    
    
    <div class="charts">
        {fig.to_html(include_plotlyjs='cdn', div_id='plotly-chart')}
    </div>
    
    <div class="footer">
        <p>PageSpeed Insights Audit Tool - Monitoring Dashboard</p>
    </div>
</body>
</html>"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Dashboard generated: {output_file}")


def generate_alert_html(metrics: Dict) -> str:
    """Generate HTML for alert banner"""
    return f"""
    <div class="alert">
        <h3>⚠️ Alert: High Failure Rate Detected</h3>
        <p>Current failure rate ({metrics['failure_rate_percent']:.1f}%) has exceeded the 20% threshold.</p>
        <p>Failed URLs: {metrics['failed_urls']} out of {metrics['analyzed_urls']} analyzed</p>
    </div>
    """


def generate_playwright_metrics_html(metrics: Dict) -> str:
    """Generate HTML for Playwright-specific metrics"""
    pw = metrics.get('playwright', {})
    if not pw:
        return ''
    
    return f"""
    <div style="margin-bottom: 30px;">
        <h2 style="color: #333; margin-bottom: 20px;">🎭 Playwright Performance Metrics</h2>
        <div class="metrics-grid">
            <div class="metric-card">
                <h3>Avg Page Load Time</h3>
                <div class="value">{pw.get('avg_page_load_time_seconds', 0):.2f}s</div>
                <div class="subvalue">{pw.get('total_page_loads', 0)} page loads</div>
            </div>
            
            <div class="metric-card">
                <h3>Avg Browser Startup</h3>
                <div class="value">{pw.get('avg_browser_startup_time_seconds', 0):.2f}s</div>
                <div class="subvalue">Cold starts only</div>
            </div>
            
            <div class="metric-card">
                <h3>Warm Start Ratio</h3>
                <div class="value success">{pw.get('warm_start_ratio_percent', 0):.1f}%</div>
                <div class="subvalue">{pw.get('warm_starts', 0)} warm / {pw.get('cold_starts', 0)} cold</div>
            </div>
            
            <div class="metric-card">
                <h3>Avg Memory Usage</h3>
                <div class="value">{pw.get('avg_memory_usage_mb', 0):.1f} MB</div>
                <div class="subvalue">Max: {pw.get('max_memory_usage_mb', 0):.1f} MB</div>
            </div>
            
            <div class="metric-card">
                <h3>Request Blocking</h3>
                <div class="value warning">{pw.get('blocking_ratio_percent', 0):.1f}%</div>
                <div class="subvalue">{pw.get('blocked_requests', 0)} / {pw.get('total_requests', 0)} blocked</div>
            </div>
            
            <div class="metric-card">
                <h3>Total Starts</h3>
                <div class="value">{pw.get('total_starts', 0)}</div>
                <div class="subvalue">Browser instances created</div>
            </div>
        </div>
    </div>
    """


def main():
    parser = argparse.ArgumentParser(
        description='Generate metrics dashboard from audit metrics'
    )
    parser.add_argument(
        '--input',
        help='Path to JSON metrics file (if not provided, uses current metrics)'
    )
    parser.add_argument(
        '--output',
        default='dashboard.html',
        help='Path to output HTML file (default: dashboard.html)'
    )
    parser.add_argument(
        '--export-prometheus',
        help='Export Prometheus metrics to file'
    )
    parser.add_argument(
        '--export-json',
        help='Export JSON metrics to file'
    )
    
    args = parser.parse_args()
    
    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: Input file not found: {args.input}")
            sys.exit(1)
        
        with open(args.input, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
        print(f"Loaded metrics from {args.input}")
    else:
        collector = get_metrics_collector()
        metrics = collector.get_metrics()
        print("Using current metrics from collector")
    
    if args.export_prometheus:
        collector = get_metrics_collector()
        collector.save_prometheus_metrics(args.export_prometheus)
        print(f"Prometheus metrics exported to {args.export_prometheus}")
    
    if args.export_json:
        if args.input:
            with open(args.export_json, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2)
        else:
            collector = get_metrics_collector()
            collector.save_json_metrics(args.export_json)
        print(f"JSON metrics exported to {args.export_json}")
    
    generate_html_dashboard(metrics, args.output)
    
    print("\nMetrics Summary:")
    print(f"  Total URLs: {metrics['total_urls']}")
    print(f"  Successful: {metrics['successful_urls']} ({metrics['success_rate_percent']:.1f}%)")
    print(f"  Failed: {metrics['failed_urls']} ({metrics['failure_rate_percent']:.1f}%)")
    print(f"  Cache Hit Ratio: {metrics['cache_hit_ratio_percent']:.1f}%")
    print(f"  Avg Processing Time: {metrics['avg_processing_time_seconds']:.1f}s")
    
    pw_metrics = metrics.get('playwright')
    if pw_metrics:
        print("\nPlaywright Performance:")
        print(f"  Avg Page Load Time: {pw_metrics.get('avg_page_load_time_seconds', 0):.2f}s")
        print(f"  Avg Browser Startup: {pw_metrics.get('avg_browser_startup_time_seconds', 0):.2f}s")
        print(f"  Warm Start Ratio: {pw_metrics.get('warm_start_ratio_percent', 0):.1f}%")
        print(f"  Avg Memory Usage: {pw_metrics.get('avg_memory_usage_mb', 0):.1f} MB")
        print(f"  Request Blocking: {pw_metrics.get('blocking_ratio_percent', 0):.1f}%")
    
    if metrics['alert_triggered']:
        print("\n⚠️  ALERT: Failure rate exceeded 20% threshold!")


if __name__ == '__main__':
    main()
