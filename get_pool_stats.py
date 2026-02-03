#!/usr/bin/env python3
"""
Utility script to display Playwright pool statistics for monitoring and debugging.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from qa import playwright_runner


def format_bytes(bytes_value):
    """Format bytes into human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} TB"


def display_pool_stats():
    """Display current Playwright pool statistics"""
    try:
        stats = playwright_runner.get_pool_stats()
        
        print("=" * 80)
        print("PLAYWRIGHT POOL STATISTICS")
        print("=" * 80)
        print()
        
        print(f"Total Instances: {stats['total_instances']}")
        print(f"Idle Instances: {stats['idle_instances']}")
        print(f"Busy Instances: {stats['busy_instances']}")
        print()
        
        print(f"Total Warm Starts: {stats['total_warm_starts']}")
        print(f"Total Cold Starts: {stats['total_cold_starts']}")
        print(f"Average Startup Time: {stats['avg_startup_time']:.2f}s")
        print()
        
        if stats['instances']:
            print("-" * 80)
            print("INSTANCE DETAILS")
            print("-" * 80)
            
            for idx, instance in enumerate(stats['instances'], 1):
                print(f"\nInstance {idx}:")
                print(f"  PID: {instance['pid']}")
                print(f"  State: {instance['state']}")
                print(f"  Memory: {instance['memory_mb']:.2f} MB")
                print(f"  Total Analyses: {instance['total_analyses']}")
                print(f"  Avg Page Load Time: {instance['avg_page_load_time']:.2f}s")
                print(f"  Failures: {instance['failures']}")
                print(f"  Request Blocking:")
                print(f"    Total Requests: {instance['blocking_stats']['total_requests']}")
                print(f"    Blocked Requests: {instance['blocking_stats']['blocked_requests']}")
                print(f"    Blocking Ratio: {instance['blocking_stats']['blocking_ratio']:.1%}")
        else:
            print("No active instances in the pool.")
        
        print()
        print("=" * 80)
        
    except Exception as e:
        print(f"Error retrieving pool statistics: {e}", file=sys.stderr)
        sys.exit(1)


def export_pool_stats_json(filepath='pool_stats.json'):
    """Export pool statistics to JSON file"""
    try:
        stats = playwright_runner.get_pool_stats()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2)
        print(f"Pool statistics exported to {filepath}")
    except Exception as e:
        print(f"Error exporting pool statistics: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Display Playwright pool statistics'
    )
    parser.add_argument(
        '--json',
        type=str,
        default=None,
        help='Export statistics to JSON file'
    )
    
    args = parser.parse_args()
    
    if args.json:
        export_pool_stats_json(args.json)
    else:
        display_pool_stats()
