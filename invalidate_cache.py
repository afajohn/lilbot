#!/usr/bin/env python3
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

from cache.cache_manager import get_cache_manager
from utils import logger


def main():
    parser = argparse.ArgumentParser(
        description='Invalidate cache entries for PageSpeed Insights results'
    )
    parser.add_argument(
        '--url',
        help='Specific URL to invalidate from cache'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Invalidate all cache entries'
    )
    
    args = parser.parse_args()
    
    if not args.url and not args.all:
        parser.error("Either --url or --all must be specified")
    
    if args.url and args.all:
        parser.error("Cannot specify both --url and --all")
    
    log = logger.setup_logger()
    cache_manager = get_cache_manager(enabled=True)
    
    if args.all:
        log.info("Invalidating all cache entries...")
        success = cache_manager.invalidate_all()
        if success:
            log.info("✓ Successfully invalidated all cache entries")
            return 0
        else:
            log.error("✗ Failed to invalidate cache entries")
            return 1
    
    if args.url:
        log.info(f"Invalidating cache for URL: {args.url}")
        if not cache_manager.exists(args.url):
            log.warning(f"No cache entry found for URL: {args.url}")
            return 0
        
        success = cache_manager.invalidate(args.url)
        if success:
            log.info(f"✓ Successfully invalidated cache for: {args.url}")
            return 0
        else:
            log.error(f"✗ Failed to invalidate cache for: {args.url}")
            return 1


if __name__ == '__main__':
    sys.exit(main())
