# Cache Guide

## Overview

The PageSpeed Insights audit tool includes a comprehensive caching layer to improve performance and reduce redundant API calls. The cache system supports both Redis (recommended for production) and file-based storage (automatic fallback).

## Features

- **Dual Backend Support**: Redis backend with automatic fallback to file-based cache
- **URL Fingerprinting**: URLs are cached with daily timestamp for cache invalidation
- **24-Hour TTL**: Default cache expiration of 24 hours (configurable)
- **LRU Eviction**: File cache uses Least Recently Used eviction (max 1000 entries)
- **Cache Invalidation API**: CLI tool to invalidate specific URLs or clear all cache
- **Thread-Safe**: All cache operations are thread-safe for concurrent execution
- **CLI Control**: `--skip-cache` flag to bypass cache when needed

## Architecture

### Cache Key Generation

Cache keys are generated using SHA-256 hash of:
```
URL + "|" + TIMESTAMP_DAY (YYYY-MM-DD)
```

This ensures:
- Same URL gets cached independently per day
- Automatic invalidation after 24 hours
- URL variations are treated as separate entries

### Backend Selection

1. **Redis Backend** (preferred):
   - Requires Redis server running
   - Configured via environment variables
   - Shared across multiple processes
   - Better performance for high concurrency

2. **File Cache Backend** (fallback):
   - No external dependencies
   - Stored in `.cache/` directory
   - LRU eviction with max 1000 entries
   - Good for single-process or low-volume usage

## Configuration

### Environment Variables

Configure cache behavior via environment variables:

```bash
# Redis Configuration (optional)
REDIS_HOST=localhost          # Default: localhost
REDIS_PORT=6379              # Default: 6379
REDIS_DB=0                   # Default: 0
REDIS_PASSWORD=              # Default: none

# File Cache Configuration (optional)
CACHE_DIR=.cache             # Default: .cache
CACHE_MAX_ENTRIES=1000       # Default: 1000
```

### .env File Example

Create a `.env` file in the project root:

```bash
# Use Redis backend
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Or configure file cache
CACHE_DIR=.cache
CACHE_MAX_ENTRIES=2000
```

## Usage

### Running Audit with Cache (Default)

Cache is enabled by default:

```bash
python run_audit.py --tab "My Tab"
```

On first run, URLs are analyzed and results cached. Subsequent runs within 24 hours will use cached results.

### Bypassing Cache

Use `--skip-cache` to force fresh analysis:

```bash
python run_audit.py --tab "My Tab" --skip-cache
```

This is useful when:
- You want the most recent PageSpeed scores
- Testing changes to a specific URL
- Cache data is suspected to be stale

### Cache Invalidation

#### Invalidate Specific URL

```bash
python invalidate_cache.py --url "https://example.com"
```

#### Invalidate All Cache

```bash
python invalidate_cache.py --all
```

### Checking Cache Status

Cache hits and misses are logged:

```
Cache HIT for URL: https://example.com
Using cached result for https://example.com
```

or

```
Cache MISS for URL: https://example.com
```

## Cache Storage Details

### Redis Backend

- Keys: `psi:<sha256_hash>`
- Values: JSON-serialized result data
- Expiration: Automatic via Redis SETEX
- Storage: In-memory Redis database

### File Cache Backend

- Location: `.cache/` directory
- Files: `<sha256_hash>.json`
- Index: `_cache_index.json` (tracks LRU order)
- Eviction: Automatic when max entries reached

## Cache Data Structure

Cached data includes:

```json
{
  "url": "https://example.com",
  "mobile_score": 85,
  "desktop_score": 92,
  "mobile_psi_url": null,
  "desktop_psi_url": null,
  "cached_at": "2024-02-03T10:30:00.000000",
  "timestamp_day": "2024-02-03"
}
```

## Best Practices

### When to Use Cache

✅ **Use cache** (default behavior) when:
- Running daily/periodic audits
- Analyzing large batches of URLs
- URLs haven't changed significantly
- Reducing load on PageSpeed Insights API

### When to Skip Cache

❌ **Skip cache** (`--skip-cache`) when:
- Testing after website changes
- Validating specific fixes
- Cache is suspected to be corrupted
- Need most recent performance data

### Redis vs File Cache

**Use Redis when**:
- Running in production environment
- High concurrency (multiple workers)
- Shared cache across multiple machines
- Large number of URLs (>1000)

**Use File Cache when**:
- Development/testing environment
- Single process execution
- Small to medium batches (<1000 URLs)
- Cannot install/run Redis

## Troubleshooting

### Redis Connection Issues

If Redis connection fails:
```
Failed to connect to Redis: [Errno 111] Connection refused
Redis backend failed, falling back to file cache
```

**Solutions**:
1. Ensure Redis server is running: `redis-cli ping`
2. Check Redis host/port configuration
3. Verify firewall rules
4. System will automatically fall back to file cache

### File Cache Issues

**Cache directory permissions**:
```bash
chmod 755 .cache
```

**Clear corrupted cache**:
```bash
python invalidate_cache.py --all
# or manually
rm -rf .cache
```

### Cache Not Working

1. Check cache is enabled (not using `--skip-cache`)
2. Verify cache directory is writable
3. Check disk space availability
4. Review logs for cache warnings

### LRU Eviction Too Aggressive

Increase max entries:
```bash
export CACHE_MAX_ENTRIES=5000
```

## Performance Impact

### Cache Hit Ratio

Monitor cache effectiveness:
- **High hit ratio** (>70%): Significant time savings
- **Low hit ratio** (<30%): Consider cache invalidation

### Time Savings

Typical PageSpeed analysis: 30-60 seconds per URL
Cache retrieval: <1 second

**Example**: 100 URLs with 80% cache hit rate
- Without cache: ~50 minutes
- With cache: ~10 minutes (80% time reduction)

## Maintenance

### Regular Cleanup

File cache is self-maintaining via LRU eviction, but you can manually clear:

```bash
# Clear all cache
python invalidate_cache.py --all

# Or delete cache directory
rm -rf .cache
```

### Redis Maintenance

Monitor Redis memory usage:
```bash
redis-cli info memory
```

Clear all PSI cache keys:
```bash
redis-cli KEYS "psi:*" | xargs redis-cli DEL
```

## Security Considerations

- Cache directory (`.cache/`) is gitignored by default
- No sensitive data is stored in cache
- Cache keys are hashed to avoid exposing URLs in Redis
- Redis password authentication supported via `REDIS_PASSWORD`

## API Reference

### CacheManager

```python
from tools.cache.cache_manager import get_cache_manager

# Get cache manager instance
cache = get_cache_manager(enabled=True)

# Get cached result
result = cache.get(url)

# Store result in cache
cache.set(url, result, ttl=86400)

# Invalidate specific URL
cache.invalidate(url)

# Clear all cache
cache.invalidate_all()

# Check if URL is cached
exists = cache.exists(url)
```

### Custom Backend

```python
from tools.cache.cache_manager import CacheManager, RedisBackend

# Use custom Redis configuration
redis_backend = RedisBackend(
    host='redis.example.com',
    port=6380,
    password='secret',
    key_prefix='myapp:'
)

cache = CacheManager(backend=redis_backend)
```

## Limitations

- Cache is day-based; same URL analyzed multiple times in one day uses same cache
- No cross-day cache warming
- File cache limited to 1000 entries by default (configurable)
- Redis cache limited by available memory
- Cache doesn't track website changes automatically
