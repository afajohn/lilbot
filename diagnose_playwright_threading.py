#!/usr/bin/env python3
"""
Playwright Threading Diagnostics Tool

This utility provides comprehensive diagnostics for threading issues in the Playwright runner.
It reports on thread IDs, event loop health, greenlet errors, and pool statistics.

Usage:
    python diagnose_playwright_threading.py
    python diagnose_playwright_threading.py --json output.json
"""

import argparse
import json
import sys
from tools.qa.playwright_runner import (
    diagnose_threading_issues,
    print_threading_diagnostics,
    get_threading_metrics,
    get_event_loop_health,
    get_pool_stats
)


def main():
    parser = argparse.ArgumentParser(
        description="Diagnose Playwright threading issues",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--json',
        type=str,
        metavar='FILE',
        help='Export diagnostics to JSON file'
    )
    parser.add_argument(
        '--metrics-only',
        action='store_true',
        help='Show only threading metrics'
    )
    parser.add_argument(
        '--health-only',
        action='store_true',
        help='Show only event loop health'
    )
    parser.add_argument(
        '--pool-only',
        action='store_true',
        help='Show only pool statistics'
    )
    
    args = parser.parse_args()
    
    if args.metrics_only:
        metrics = get_threading_metrics()
        print("\nThreading Metrics:")
        print(json.dumps(metrics, indent=2))
    elif args.health_only:
        health = get_event_loop_health()
        print("\nEvent Loop Health:")
        print(json.dumps(health, indent=2))
    elif args.pool_only:
        pool = get_pool_stats()
        print("\nPool Statistics:")
        print(json.dumps(pool, indent=2))
    else:
        diagnosis = diagnose_threading_issues()
        
        if args.json:
            with open(args.json, 'w') as f:
                json.dump(diagnosis, f, indent=2, default=str)
            print(f"Diagnostics exported to {args.json}")
        else:
            print_threading_diagnostics()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
