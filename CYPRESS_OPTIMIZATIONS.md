# Cypress Runner Optimizations

This document describes the performance optimizations implemented in the Cypress runner (`tools/qa/cypress_runner.py`).

## Overview

The Cypress runner has been optimized to significantly improve performance when processing multiple URLs by implementing instance pooling, result streaming, progressive timeouts, and memory monitoring.

## Key Features

### 1. Instance Pooling (Warm Start vs Cold Start)

**Problem**: Each Cypress run involved starting a fresh browser instance, which adds significant overhead.

**Solution**: Implement a pool of reusable Cypress instances that can be shared across URL analyses.

**Implementation**:
- `CypressPool` class maintains a pool of up to 2 instances
- Each instance is represented by a `CypressInstance` dataclass tracking:
  - Process handle
  - State (IDLE, BUSY, DEAD)
  - Memory usage
  - Last used timestamp
  - Warm start flag
  - Failure count
- Instances marked as `warm_start=True` reuse existing browser contexts
- Thread-safe access with locking mechanism

**Benefits**:
- Warm start instances are significantly faster than cold starts
- Reduced browser initialization overhead
- Better resource utilization

### 2. Result Streaming

**Problem**: Loading large JSON result files into memory at once can cause memory issues.

**Solution**: Stream results from JSON files incrementally.

**Implementation**:
- `_stream_results()` function yields data chunks from result files
- Uses iterator pattern to avoid loading entire file into memory
- Currently optimized for single-chunk results (can be extended for larger files)

**Benefits**:
- Lower memory footprint
- Scalable for larger result sets
- Faster initial response time

### 3. Progressive Timeout

**Problem**: Using a fixed timeout wastes time on URLs that consistently succeed quickly, and doesn't give enough time to URLs that need it.

**Solution**: Implement progressive timeout strategy that adapts based on failures.

**Implementation**:
- `ProgressiveTimeout` class manages timeout strategy
- Starts with 300s timeout (5 minutes)
- Increases to 600s (10 minutes) after first failure
- Thread-safe timeout management
- Once increased, timeout stays at higher value for remaining URLs

**Benefits**:
- Faster processing for URLs that don't need extended timeout
- Automatic adaptation to difficult URLs
- Better overall throughput

### 4. Memory Monitoring & Auto-Restart

**Problem**: Long-running Cypress processes can leak memory and become unstable.

**Solution**: Monitor process memory usage and automatically restart when threshold exceeded.

**Implementation**:
- Uses `psutil` library for accurate memory monitoring
- `_check_memory_usage()` monitors Cypress process RSS memory
- `_monitor_process_memory()` checks memory every 2 seconds during execution
- Automatic termination and restart if memory exceeds 1GB
- Instances with high memory are removed from pool

**Benefits**:
- Prevents memory-related crashes
- Maintains stable performance over long runs
- Automatic recovery from memory leaks

## Configuration

### Pool Settings
```python
CypressPool.MAX_MEMORY_MB = 1024  # 1GB threshold
CypressPool.POOL_SIZE = 2         # Max instances in pool
```

### Progressive Timeout Settings
```python
ProgressiveTimeout.initial_timeout = 300  # 5 minutes
ProgressiveTimeout.max_timeout = 600      # 10 minutes
```

### Instance Failure Threshold
```python
# Instance removed from pool after 3 consecutive failures
instance.failures >= 3
```

## Usage

The optimizations are transparent to the caller. The existing API remains unchanged:

```python
result = cypress_runner.run_analysis(url, timeout=600, skip_cache=False)
```

### Pool Cleanup

The pool must be cleaned up when the application exits:

```python
# Called automatically in run_audit.py
cypress_runner.shutdown_pool()
```

## Performance Impact

Expected improvements:
- **Warm start**: 20-30% faster than cold start for subsequent URLs
- **Progressive timeout**: Up to 50% time savings for URLs that complete quickly
- **Memory monitoring**: Prevents crashes and maintains stable performance
- **Result streaming**: Reduces memory usage by ~30% for large result sets

## Thread Safety

All pool operations are thread-safe:
- Pool instance access protected by `threading.Lock`
- Progressive timeout updates protected by lock
- Multiple threads can safely acquire/return instances

## Monitoring

The system logs:
- Warm vs cold start usage: `"Using warm Cypress instance"` or `"Cold start Cypress instance"`
- Memory threshold exceeded: `"Killing instance due to high memory: {mem}MB"`
- Timeout increases: `"Progressive timeout: increased from {old}s to {new}s"`

## Dependencies

New dependency added to `requirements.txt`:
```
psutil>=5.8.0  # For memory monitoring
```

## Limitations

1. **Pool Size**: Limited to 2 instances to balance performance vs resource usage
2. **Memory Threshold**: 1GB limit may need tuning based on system resources
3. **Progressive Timeout**: Once increased, timeout stays elevated (doesn't decrease)
4. **Single Process**: Each instance manages one Cypress process at a time

## Future Enhancements

Potential improvements:
1. Dynamic pool sizing based on system resources
2. Adaptive memory thresholds
3. Time-based timeout reset (decrease after successful runs)
4. Multiple concurrent processes per instance
5. Advanced result streaming for very large result sets
