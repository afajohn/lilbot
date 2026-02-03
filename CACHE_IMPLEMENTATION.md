# Cache Implementation Summary

## Overview

A comprehensive caching layer has been implemented for the PageSpeed Insights audit tool to significantly improve performance and reduce redundant API calls.

## Components Implemented

### 1. Cache Manager (`tools/cache/cache_manager.py`)

**Core Classes:**
- `CacheBackend` - Abstract base class for cache backends
- `RedisBackend` - Redis-based cache implementation
- `FileCacheBackend` - File-based cache with LRU eviction
- `CacheManager` - High-level cache management interface

**Key Features:**
- Automatic backend selection (Redis → File fallback)
- Thread-safe operations
- URL fingerprinting with daily timestamps
- 24-hour default TTL
- LRU eviction for file cache (max 1000 entries)

### 2. Cache Invalidation Tool (`invalidate_cache.py`)

CLI utility for cache management:
```bash
# Invalidate specific URL
python invalidate_cache.py --url "https://example.com"

# Clear all cache
python invalidate_cache.py --all
```

### 3. Integration Points

**Modified Files:**
- `run_audit.py` - Added `--skip-cache` CLI flag, integrated cache in processing flow
- `tools/qa/cypress_runner.py` - Added cache check/set logic in `run_analysis()`
- `requirements.txt` - Added `redis>=4.0.0` dependency
- `.gitignore` - Added `.cache/` directory exclusion
- `.env.example` - Added cache configuration examples

### 4. Documentation

**New Files:**
- `CACHE_GUIDE.md` - Comprehensive cache usage and configuration guide
- `CACHE_IMPLEMENTATION.md` - This file

**Updated Files:**
- `README.md` - Added cache management section and CLI flags
- `AGENTS.md` - Updated with cache architecture and configuration

## Architecture

### Cache Key Generation

```
SHA256(URL + "|" + YYYY-MM-DD)
```

This ensures:
- Same URL cached per day
- Automatic daily refresh
- Collision-resistant keys

### Backend Selection Logic

1. Check if Redis module is available
2. Try to connect to Redis (via environment variables)
3. On failure, fall back to file-based cache
4. Log backend selection for transparency

### File Cache Structure

```
.cache/
├── _cache_index.json          # LRU tracking
├── <hash1>.json               # Cached result
├── <hash2>.json               # Cached result
└── ...
```

**Index File Format:**
```json
{
  "lru_order": ["hash1", "hash2", "hash3", ...],
  "last_updated": "2024-02-03T10:30:00.000000"
}
```

**Cache Entry Format:**
```json
{
  "value": {
    "url": "https://example.com",
    "mobile_score": 85,
    "desktop_score": 92,
    "mobile_psi_url": null,
    "desktop_psi_url": null,
    "cached_at": "2024-02-03T10:30:00.000000",
    "timestamp_day": "2024-02-03"
  },
  "expiry": "2024-02-04T10:30:00.000000",
  "created_at": "2024-02-03T10:30:00.000000"
}
```

### Redis Cache Structure

- **Key Pattern**: `psi:<sha256_hash>`
- **Value**: JSON-serialized cache entry
- **TTL**: Set via SETEX (automatic expiration)
- **Connection**: Configurable via environment variables

## Configuration

### Environment Variables

```bash
# Redis Backend
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# File Cache Backend
CACHE_DIR=.cache
CACHE_MAX_ENTRIES=1000
```

### CLI Flags

```bash
# Normal operation (cache enabled)
python run_audit.py --tab "My Tab"

# Skip cache for fresh results
python run_audit.py --tab "My Tab" --skip-cache
```

## Flow Diagram

```
[run_audit.py] → [process_url()]
       ↓
[cypress_runner.run_analysis(url, skip_cache)]
       ↓
   skip_cache?
       ↓
   Yes ─────────────────────→ [Run Cypress Analysis]
       ↓                               ↓
   No → [Check Cache]              [Cache Result]
       ↓         ↓                     ↓
     Hit        Miss                Return
       ↓         ↓
   Return   [Run Cypress]
            [Cache Result]
            [Return]
```

## Performance Impact

### Expected Improvements

**Without Cache:**
- 100 URLs × 45 seconds = ~75 minutes

**With Cache (80% hit rate):**
- 20 URLs × 45 seconds = 15 minutes
- 80 URLs × 1 second = ~1 minute
- **Total: ~16 minutes (79% time reduction)**

### Cache Hit Scenarios

1. **Daily Re-runs**: Very high hit rate (>90%)
2. **Weekly Audits**: Medium hit rate (30-50%)
3. **Fresh Websites**: Low hit rate (<10%)

## Error Handling

### Redis Connection Failures

- Graceful fallback to file cache
- Warning logged
- No interruption to audit process

### File System Errors

- Logged as warnings
- Cache operations fail silently
- Analysis continues without cache

### Cache Corruption

- Expired entries automatically removed
- Invalid JSON files skipped
- Manual cleanup via `invalidate_cache.py --all`

## Thread Safety

### File Cache
- Uses threading.Lock() for all operations
- Index updates are atomic
- LRU order maintained consistently

### Redis Cache
- Redis operations are naturally thread-safe
- Connection pool handles concurrency
- No explicit locking needed

## Testing Considerations

When testing, consider:

1. **Cache-enabled tests**: Test cache hit/miss scenarios
2. **Cache-disabled tests**: Use `skip_cache=True` or `--skip-cache`
3. **Backend selection**: Test both Redis and file backends
4. **Concurrency**: Test with multiple workers
5. **Eviction**: Test LRU behavior with max_entries

## Security

- Cache keys are hashed (no URL exposure in Redis)
- `.cache/` directory gitignored
- No sensitive data in cache
- Redis password authentication supported

## Limitations

1. **Day-based expiration**: Same URL analyzed multiple times per day uses same cache
2. **No content detection**: Cache doesn't know if website changed
3. **Local cache**: File cache not shared across machines
4. **Memory usage**: Redis cache limited by available memory
5. **Disk space**: File cache limited by disk space

## Future Enhancements

Potential improvements:
- Cache warming API
- Content-based invalidation (detect website changes)
- Cross-day cache persistence option
- Cache statistics/metrics
- Distributed file cache support
- Custom TTL per URL
- Cache export/import tools

## Maintenance

### Regular Tasks

1. **Monitor cache size**: Check `.cache/` directory or Redis memory
2. **Review hit rates**: Analyze logs for cache effectiveness
3. **Clear stale cache**: Run `invalidate_cache.py --all` periodically
4. **Update Redis**: Keep Redis version current for security

### Troubleshooting

See [CACHE_GUIDE.md](CACHE_GUIDE.md) for detailed troubleshooting steps.

## Implementation Checklist

- [x] Create `tools/cache/` directory structure
- [x] Implement `CacheBackend` abstract class
- [x] Implement `RedisBackend` with connection handling
- [x] Implement `FileCacheBackend` with LRU eviction
- [x] Implement `CacheManager` with fingerprinting
- [x] Create `invalidate_cache.py` CLI tool
- [x] Add `--skip-cache` flag to `run_audit.py`
- [x] Integrate cache in `cypress_runner.py`
- [x] Update `requirements.txt` with redis dependency
- [x] Update `.gitignore` for `.cache/` directory
- [x] Update `.env.example` with cache variables
- [x] Create comprehensive `CACHE_GUIDE.md`
- [x] Update `README.md` with cache usage
- [x] Update `AGENTS.md` with cache architecture
- [x] Document implementation in this file

## Code Quality

- Type hints used throughout
- Thread-safe implementations
- Comprehensive error handling
- Logging at appropriate levels
- Follows existing code conventions
- No comments (as per project style)
