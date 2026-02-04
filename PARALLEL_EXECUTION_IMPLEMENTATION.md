# Parallel Execution Implementation

## Overview
Refactored `playwright_runner.py` to support bounded parallel execution with 2-3 concurrent browser contexts within a single browser process.

## Key Changes

### 1. Multi-Context Pool Architecture

**Before:** Single browser instance with single context
**After:** Single browser with multiple concurrent contexts (2-3)

#### PlaywrightPool Changes
- Changed from `self.instance` (single) to `self.contexts: List[PlaywrightInstance]` (multiple)
- Added `self._browser: Optional[Browser]` to maintain shared browser instance
- Added `self.max_concurrent_contexts: int` parameter (default: 3)
- Added `self._semaphore: asyncio.Semaphore` for concurrency control

#### Key Methods Updated
- `get_instance()`: Now iterates through contexts to find idle ones
- `return_instance()`: Returns context to pool instead of replacing singleton
- `create_instance()`: Creates new browser context (not new browser)
- `force_refresh_instance()`: Refreshes context, not entire browser
- `cleanup_dead_instances()`: Cleans up multiple contexts
- `shutdown()`: Closes all contexts and shared browser

### 2. Instance-Level Locks

Added `context_lock: asyncio.Lock` to `PlaywrightInstance` dataclass to prevent concurrent access conflicts:

```python
@dataclass
class PlaywrightInstance:
    # ... existing fields ...
    context_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
```

**Usage:** Protects `context.new_page()` calls:
```python
async with instance.context_lock:
    page = await context.new_page()
```

### 3. Batch Analysis Functions

#### `run_analysis_batch()` - Public API
```python
async def run_analysis_batch(
    urls: List[str], 
    concurrency: int = 2, 
    timeout: int = 600, 
    skip_cache: bool = False, 
    force_retry: bool = False
) -> List[Dict[str, Optional[int | str]]]
```

- Validates Playwright availability
- Submits batch request to event loop thread
- Returns list of results (exceptions for failures)

#### `_run_analysis_batch_async()` - Internal Implementation
```python
async def _run_analysis_batch_async(
    urls: List[str], 
    timeout: int, 
    force_retry: bool, 
    concurrency: int, 
    pool: PlaywrightPool
) -> List[Dict[str, Optional[int | str]]]
```

- Creates `asyncio.Semaphore(concurrency)` for bounded parallelism
- Uses `asyncio.gather(..., return_exceptions=True)` for parallel execution
- Each URL analysis wrapped with semaphore acquisition

### 4. Request Handling Updates

#### New Request Type
```python
@dataclass
class BatchAnalysisRequest:
    urls: List[str]
    timeout: int
    force_retry: bool
    concurrency: int
    future: Future
```

#### PlaywrightEventLoopThread Changes
- Added `max_concurrent_contexts` parameter
- Updated `request_queue` type to accept `AnalysisRequest | BatchAnalysisRequest`
- Added `submit_batch_analysis()` method
- Updated `_process_requests()` to handle both request types

### 5. Global Configuration

Added new configuration functions:
```python
def set_max_concurrent_contexts(max_contexts: int)  # Sets 1-5, default 3
def get_max_concurrent_contexts() -> int
```

Global variables:
```python
_max_concurrent_contexts = 3  # Default value
```

### 6. Pool Statistics Updates

Changed from single-instance to multi-context stats:
```python
{
    'mode': 'multi-context',  # Changed from 'single-instance'
    'max_concurrent_contexts': 3,
    'total_contexts': 2,  # Changed from 'total_instances'
    'idle_contexts': 1,   # Changed from 'idle_instances'
    'busy_contexts': 1,   # Changed from 'busy_instances'
    'contexts': [...]     # Changed from 'instances'
}
```

## Architecture Diagram

```
Main Thread
    ↓
Event Loop Thread (Single)
    ↓
PlaywrightPool
    ├─ Shared Browser Instance
    └─ Multiple Browser Contexts (2-3)
        ├─ Context 1 (with lock)
        ├─ Context 2 (with lock)
        └─ Context 3 (with lock)

Semaphore Controls Concurrency
    ↓
asyncio.gather() with return_exceptions=True
```

## Concurrency Control Flow

1. **Semaphore Acquisition**: `async with semaphore:` limits to N concurrent tasks
2. **Context Pool**: Reuses idle contexts or creates new ones (up to max)
3. **Context Lock**: `async with instance.context_lock:` protects page creation
4. **Parallel Execution**: `asyncio.gather()` runs multiple URL analyses
5. **Error Handling**: Exceptions captured and returned in results list

## Benefits

1. **Bounded Parallelism**: 2-3x throughput with controlled resource usage
2. **Memory Efficiency**: Single browser process, multiple lightweight contexts
3. **Thread Safety**: Locks prevent context conflicts
4. **Error Isolation**: Failed analyses don't affect others
5. **Backward Compatible**: Existing `run_analysis()` still works sequentially

## Usage Examples

### Sequential (Existing)
```python
result = run_analysis("https://example.com")
```

### Parallel (New)
```python
urls = ["https://example1.com", "https://example2.com", "https://example3.com"]
results = await run_analysis_batch(urls, concurrency=2)

for i, result in enumerate(results):
    if isinstance(result, Exception):
        print(f"URL {urls[i]} failed: {result}")
    else:
        print(f"URL {urls[i]} scores: {result}")
```

### Configuration
```python
# Set max concurrent contexts (1-5)
set_max_concurrent_contexts(2)  # More conservative

# Check current setting
max_contexts = get_max_concurrent_contexts()
```

## Testing Recommendations

1. **Unit Tests**: Test semaphore limiting with mock contexts
2. **Integration Tests**: Verify parallel execution with real URLs
3. **Stress Tests**: Test with 10+ URLs to verify context reuse
4. **Error Tests**: Verify exception handling and isolation
5. **Lock Tests**: Verify no race conditions with concurrent page creation

## Performance Expectations

- **Sequential**: ~10-15 min/URL = 4-6 URLs/hour
- **Parallel (concurrency=2)**: ~8-12 URLs/hour (2x improvement)
- **Parallel (concurrency=3)**: ~12-18 URLs/hour (3x improvement)

Actual performance depends on:
- Network latency
- PageSpeed Insights response time
- System memory and CPU
- Browser stability under load
