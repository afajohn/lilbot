#!/usr/bin/env python3
import json
import argparse
from datetime import datetime
from typing import Optional


def parse_timestamp(ts_str: str) -> datetime:
    return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))


def format_timestamp(ts_str: str) -> str:
    dt = parse_timestamp(ts_str)
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def query_audit_trail(
    audit_file: str,
    spreadsheet_id: Optional[str] = None,
    tab_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    operation: Optional[str] = None,
    limit: Optional[int] = None
):
    try:
        with open(audit_file, 'r', encoding='utf-8') as f:
            entries = []
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    
                    if spreadsheet_id and entry.get('spreadsheet_id') != spreadsheet_id:
                        continue
                    
                    if tab_name and entry.get('tab_name') != tab_name:
                        continue
                    
                    if operation and entry.get('operation') != operation:
                        continue
                    
                    if start_date:
                        entry_date = parse_timestamp(entry['timestamp'])
                        start_dt = datetime.fromisoformat(start_date)
                        if entry_date < start_dt:
                            continue
                    
                    if end_date:
                        entry_date = parse_timestamp(entry['timestamp'])
                        end_dt = datetime.fromisoformat(end_date)
                        if entry_date > end_dt:
                            continue
                    
                    entries.append(entry)
                    
                except json.JSONDecodeError:
                    continue
            
            if limit:
                entries = entries[-limit:]
            
            return entries
    
    except FileNotFoundError:
        print(f"Error: Audit trail file not found: {audit_file}")
        return []


def main():
    parser = argparse.ArgumentParser(
        description='Query the audit trail for spreadsheet modifications'
    )
    parser.add_argument(
        '--audit-file',
        default='audit_trail.jsonl',
        help='Path to the audit trail file (default: audit_trail.jsonl)'
    )
    parser.add_argument(
        '--spreadsheet-id',
        help='Filter by spreadsheet ID'
    )
    parser.add_argument(
        '--tab',
        help='Filter by tab name'
    )
    parser.add_argument(
        '--operation',
        choices=['update', 'batch_update'],
        help='Filter by operation type'
    )
    parser.add_argument(
        '--start-date',
        help='Filter entries after this date (ISO format: 2024-01-01)'
    )
    parser.add_argument(
        '--end-date',
        help='Filter entries before this date (ISO format: 2024-12-31)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of results (shows most recent)'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'summary', 'detailed'],
        default='summary',
        help='Output format (default: summary)'
    )
    parser.add_argument(
        '--count',
        action='store_true',
        help='Only show count of matching entries'
    )
    
    args = parser.parse_args()
    
    entries = query_audit_trail(
        audit_file=args.audit_file,
        spreadsheet_id=args.spreadsheet_id,
        tab_name=args.tab,
        start_date=args.start_date,
        end_date=args.end_date,
        operation=args.operation,
        limit=args.limit
    )
    
    if not entries:
        print("No matching entries found.")
        return 0
    
    if args.count:
        print(f"Total entries: {len(entries)}")
        return 0
    
    if args.format == 'json':
        for entry in entries:
            print(json.dumps(entry))
    
    elif args.format == 'summary':
        print(f"Found {len(entries)} entries:\n")
        for entry in entries:
            ts = format_timestamp(entry['timestamp'])
            op = entry['operation']
            tab = entry['tab_name']
            row = entry['row']
            col = entry['column']
            value_preview = entry['value'][:50] + '...' if len(entry['value']) > 50 else entry['value']
            print(f"{ts} | {op:12s} | {tab} | {col}{row} | {value_preview}")
    
    elif args.format == 'detailed':
        print(f"Found {len(entries)} entries:\n")
        for i, entry in enumerate(entries, 1):
            print(f"Entry {i}:")
            print(f"  Timestamp:      {format_timestamp(entry['timestamp'])}")
            print(f"  Operation:      {entry['operation']}")
            print(f"  Spreadsheet ID: {entry['spreadsheet_id']}")
            print(f"  Tab:            {entry['tab_name']}")
            print(f"  Location:       {entry['column']}{entry['row']}")
            print(f"  Value:          {entry['value']}")
            print(f"  User:           {entry['user']}")
            if 'metadata' in entry:
                print(f"  Metadata:       {json.dumps(entry['metadata'])}")
            print()
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
