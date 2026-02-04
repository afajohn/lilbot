import threading
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json


class MetricsCollector:
    """
    Collects and exports metrics in Prometheus-compatible format.
    Tracks success/failure rates, processing time, API quota usage, cache hit ratio,
    and Playwright-specific metrics (page load time, browser startup time, memory per instance).
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()
        
        self._total_urls = 0
        self._successful_urls = 0
        self._failed_urls = 0
        self._skipped_urls = 0
        
        self._cache_hits = 0
        self._cache_misses = 0
        
        self._api_calls_sheets = 0
        self._api_calls_cypress = 0
        
        self._processing_times: List[float] = []
        
        self._failure_reasons: Dict[str, int] = defaultdict(int)
        
        self._url_results: List[Dict] = []
        
        self._alert_triggered = False
        self._alert_threshold = 0.20
        
        self._playwright_page_load_times: List[float] = []
        self._playwright_browser_startup_times: List[float] = []
        self._playwright_memory_usage: List[float] = []
        self._playwright_warm_starts = 0
        self._playwright_cold_starts = 0
        self._playwright_total_requests = 0
        self._playwright_blocked_requests = 0
        self._playwright_blocked_by_type: Dict[str, int] = defaultdict(int)
        self._playwright_instance_refreshes = 0
        self._playwright_memory_before_cleanup: List[float] = []
        self._playwright_memory_after_cleanup: List[float] = []
        
        self._threading_greenlet_errors = 0
        self._threading_conflicts = 0
        self._threading_event_loop_failures = 0
        
        self._inter_url_delays: List[float] = []
        
        self._sequential_processing_start: Optional[float] = None
        self._sequential_urls_processed = 0
        self._sequential_last_url_time: Optional[float] = None
        
    def record_url_start(self):
        """Record start of URL processing"""
        with self._lock:
            self._total_urls += 1
        return time.time()
    
    def record_url_success(self, start_time: float, from_cache: bool = False):
        """Record successful URL processing"""
        with self._lock:
            self._successful_urls += 1
            processing_time = time.time() - start_time
            self._processing_times.append(processing_time)
            
            if from_cache:
                self._cache_hits += 1
            else:
                self._cache_misses += 1
            
            self._url_results.append({
                'timestamp': datetime.now().isoformat(),
                'status': 'success',
                'processing_time': processing_time,
                'from_cache': from_cache
            })
            
            if len(self._url_results) > 10000:
                self._url_results = self._url_results[-10000:]
            
            self._check_failure_rate()
    
    def record_url_failure(self, start_time: float, reason: str = 'unknown'):
        """Record failed URL processing"""
        with self._lock:
            self._failed_urls += 1
            processing_time = time.time() - start_time
            self._processing_times.append(processing_time)
            self._failure_reasons[reason] += 1
            
            self._url_results.append({
                'timestamp': datetime.now().isoformat(),
                'status': 'failed',
                'processing_time': processing_time,
                'reason': reason
            })
            
            if len(self._url_results) > 10000:
                self._url_results = self._url_results[-10000:]
            
            self._check_failure_rate()
    
    def record_url_skipped(self):
        """Record skipped URL"""
        with self._lock:
            self._skipped_urls += 1
            self._url_results.append({
                'timestamp': datetime.now().isoformat(),
                'status': 'skipped'
            })
            
            if len(self._url_results) > 10000:
                self._url_results = self._url_results[-10000:]
    
    def record_cache_hit(self):
        """Record cache hit"""
        with self._lock:
            self._cache_hits += 1
    
    def record_cache_miss(self):
        """Record cache miss"""
        with self._lock:
            self._cache_misses += 1
    
    def record_api_call_sheets(self, count: int = 1):
        """Record Google Sheets API call(s)"""
        with self._lock:
            self._api_calls_sheets += count
    
    def record_api_call_cypress(self, count: int = 1):
        """Record Cypress/PageSpeed API call(s)"""
        with self._lock:
            self._api_calls_cypress += count
    
    def record_playwright_metrics(
        self,
        page_load_time: float,
        browser_startup_time: float,
        memory_mb: float,
        warm_start: bool,
        blocked_requests: int = 0,
        total_requests: int = 0,
        memory_before_cleanup: Optional[float] = None,
        memory_after_cleanup: Optional[float] = None
    ):
        """
        Record Playwright-specific performance metrics.
        
        Args:
            page_load_time: Time taken to load and analyze the page (seconds)
            browser_startup_time: Time taken to start the browser (seconds, 0 for warm starts)
            memory_mb: Current memory usage of the browser instance (MB)
            warm_start: Whether this was a warm start (reused instance)
            blocked_requests: Number of requests blocked by resource interception
            total_requests: Total number of requests made
            memory_before_cleanup: Memory usage before cleanup (MB)
            memory_after_cleanup: Memory usage after cleanup (MB)
        """
        with self._lock:
            self._playwright_page_load_times.append(page_load_time)
            if browser_startup_time > 0:
                self._playwright_browser_startup_times.append(browser_startup_time)
            self._playwright_memory_usage.append(memory_mb)
            
            if memory_before_cleanup is not None:
                self._playwright_memory_before_cleanup.append(memory_before_cleanup)
            if memory_after_cleanup is not None:
                self._playwright_memory_after_cleanup.append(memory_after_cleanup)
            
            if warm_start:
                self._playwright_warm_starts += 1
            else:
                self._playwright_cold_starts += 1
            
            self._playwright_total_requests += total_requests
            self._playwright_blocked_requests += blocked_requests
            
            if len(self._playwright_page_load_times) > 10000:
                self._playwright_page_load_times = self._playwright_page_load_times[-10000:]
            if len(self._playwright_browser_startup_times) > 10000:
                self._playwright_browser_startup_times = self._playwright_browser_startup_times[-10000:]
            if len(self._playwright_memory_usage) > 10000:
                self._playwright_memory_usage = self._playwright_memory_usage[-10000:]
            if len(self._playwright_memory_before_cleanup) > 10000:
                self._playwright_memory_before_cleanup = self._playwright_memory_before_cleanup[-10000:]
            if len(self._playwright_memory_after_cleanup) > 10000:
                self._playwright_memory_after_cleanup = self._playwright_memory_after_cleanup[-10000:]
    
    def record_threading_metrics(self, greenlet_errors: int = 0, thread_conflicts: int = 0, event_loop_failures: int = 0):
        """Record threading-related metrics"""
        with self._lock:
            self._threading_greenlet_errors += greenlet_errors
            self._threading_conflicts += thread_conflicts
            self._threading_event_loop_failures += event_loop_failures
    
    def record_browser_refresh(self):
        """Record browser instance refresh"""
        with self._lock:
            self._playwright_instance_refreshes += 1
    
    def record_inter_url_delay(self, delay_seconds: float):
        """Record inter-URL delay time"""
        with self._lock:
            self._inter_url_delays.append(delay_seconds)
            if len(self._inter_url_delays) > 10000:
                self._inter_url_delays = self._inter_url_delays[-10000:]
    
    def start_sequential_processing(self):
        """Mark the start of sequential processing"""
        with self._lock:
            self._sequential_processing_start = time.time()
            self._sequential_urls_processed = 0
            self._sequential_last_url_time = time.time()
    
    def record_sequential_url_processed(self):
        """Record that a URL was processed in sequential mode"""
        with self._lock:
            self._sequential_urls_processed += 1
            self._sequential_last_url_time = time.time()
    
    def get_sequential_processing_stats(self) -> Dict:
        """Get sequential processing statistics"""
        with self._lock:
            if self._sequential_processing_start is None:
                return {
                    'active': False,
                    'urls_per_minute': 0.0,
                    'estimated_completion_time_seconds': 0.0,
                    'elapsed_time_seconds': 0.0,
                    'urls_processed': 0
                }
            
            elapsed = time.time() - self._sequential_processing_start
            urls_per_minute = (self._sequential_urls_processed / elapsed * 60) if elapsed > 0 else 0.0
            
            return {
                'active': True,
                'urls_per_minute': urls_per_minute,
                'elapsed_time_seconds': elapsed,
                'urls_processed': self._sequential_urls_processed
            }
    
    def _check_failure_rate(self):
        """Check if failure rate exceeds alert threshold"""
        analyzed = self._successful_urls + self._failed_urls
        if analyzed >= 10:
            failure_rate = self._failed_urls / analyzed
            if failure_rate > self._alert_threshold and not self._alert_triggered:
                self._alert_triggered = True
                self._trigger_alert(failure_rate)
    
    def _trigger_alert(self, failure_rate: float):
        """Trigger alert for high failure rate"""
        from tools.utils.logger import get_logger
        logger = get_logger()
        logger.warning(
            f"ALERT: Failure rate exceeded threshold! "
            f"Current rate: {failure_rate*100:.1f}% (threshold: {self._alert_threshold*100:.1f}%)",
            extra={
                'alert_type': 'high_failure_rate',
                'failure_rate': failure_rate,
                'threshold': self._alert_threshold,
                'failed_count': self._failed_urls,
                'successful_count': self._successful_urls
            }
        )
    
    def get_metrics(self) -> Dict:
        """Get all metrics as a dictionary"""
        with self._lock:
            elapsed_time = time.time() - self._start_time
            analyzed = self._successful_urls + self._failed_urls
            total_cache_checks = self._cache_hits + self._cache_misses
            
            success_rate = (
                self._successful_urls / analyzed * 100
                if analyzed > 0 else 0.0
            )
            
            failure_rate = (
                self._failed_urls / analyzed * 100
                if analyzed > 0 else 0.0
            )
            
            cache_hit_ratio = (
                self._cache_hits / total_cache_checks * 100
                if total_cache_checks > 0 else 0.0
            )
            
            avg_processing_time = (
                sum(self._processing_times) / len(self._processing_times)
                if self._processing_times else 0.0
            )
            
            avg_page_load_time = (
                sum(self._playwright_page_load_times) / len(self._playwright_page_load_times)
                if self._playwright_page_load_times else 0.0
            )
            
            avg_browser_startup_time = (
                sum(self._playwright_browser_startup_times) / len(self._playwright_browser_startup_times)
                if self._playwright_browser_startup_times else 0.0
            )
            
            avg_memory_usage = (
                sum(self._playwright_memory_usage) / len(self._playwright_memory_usage)
                if self._playwright_memory_usage else 0.0
            )
            
            max_memory_usage = (
                max(self._playwright_memory_usage)
                if self._playwright_memory_usage else 0.0
            )
            
            min_memory_usage = (
                min(self._playwright_memory_usage)
                if self._playwright_memory_usage else 0.0
            )
            
            total_starts = self._playwright_warm_starts + self._playwright_cold_starts
            warm_start_ratio = (
                self._playwright_warm_starts / total_starts * 100
                if total_starts > 0 else 0.0
            )
            
            blocking_ratio = (
                self._playwright_blocked_requests / self._playwright_total_requests * 100
                if self._playwright_total_requests > 0 else 0.0
            )
            
            avg_memory_before_cleanup = (
                sum(self._playwright_memory_before_cleanup) / len(self._playwright_memory_before_cleanup)
                if self._playwright_memory_before_cleanup else 0.0
            )
            
            avg_memory_after_cleanup = (
                sum(self._playwright_memory_after_cleanup) / len(self._playwright_memory_after_cleanup)
                if self._playwright_memory_after_cleanup else 0.0
            )
            
            avg_memory_saved_cleanup = avg_memory_before_cleanup - avg_memory_after_cleanup
            
            avg_inter_url_delay = (
                sum(self._inter_url_delays) / len(self._inter_url_delays)
                if self._inter_url_delays else 0.0
            )
            
            total_inter_url_delay = sum(self._inter_url_delays)
            
            sequential_stats = self.get_sequential_processing_stats()
            
            return {
                'uptime_seconds': elapsed_time,
                'total_urls': self._total_urls,
                'successful_urls': self._successful_urls,
                'failed_urls': self._failed_urls,
                'skipped_urls': self._skipped_urls,
                'analyzed_urls': analyzed,
                'success_rate_percent': success_rate,
                'failure_rate_percent': failure_rate,
                'cache_hits': self._cache_hits,
                'cache_misses': self._cache_misses,
                'cache_hit_ratio_percent': cache_hit_ratio,
                'api_calls_sheets': self._api_calls_sheets,
                'api_calls_cypress': self._api_calls_cypress,
                'total_api_calls': self._api_calls_sheets + self._api_calls_cypress,
                'avg_processing_time_seconds': avg_processing_time,
                'failure_reasons': dict(self._failure_reasons),
                'alert_triggered': self._alert_triggered,
                'playwright': {
                    'avg_page_load_time_seconds': avg_page_load_time,
                    'avg_browser_startup_time_seconds': avg_browser_startup_time,
                    'avg_memory_usage_mb': avg_memory_usage,
                    'max_memory_usage_mb': max_memory_usage,
                    'min_memory_usage_mb': min_memory_usage,
                    'avg_memory_before_cleanup_mb': avg_memory_before_cleanup,
                    'avg_memory_after_cleanup_mb': avg_memory_after_cleanup,
                    'avg_memory_saved_cleanup_mb': avg_memory_saved_cleanup,
                    'warm_starts': self._playwright_warm_starts,
                    'cold_starts': self._playwright_cold_starts,
                    'total_starts': total_starts,
                    'warm_start_ratio_percent': warm_start_ratio,
                    'total_requests': self._playwright_total_requests,
                    'blocked_requests': self._playwright_blocked_requests,
                    'blocking_ratio_percent': blocking_ratio,
                    'total_page_loads': len(self._playwright_page_load_times),
                    'instance_refreshes': self._playwright_instance_refreshes
                },
                'threading': {
                    'greenlet_errors': self._threading_greenlet_errors,
                    'thread_conflicts': self._threading_conflicts,
                    'event_loop_failures': self._threading_event_loop_failures
                },
                'inter_url_delays': {
                    'avg_delay_seconds': avg_inter_url_delay,
                    'total_delay_seconds': total_inter_url_delay,
                    'count': len(self._inter_url_delays)
                },
                'sequential_processing': sequential_stats
            }
    
    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus text format.
        
        Returns:
            String in Prometheus exposition format
        """
        metrics = self.get_metrics()
        lines = []
        
        lines.append("# HELP psi_audit_uptime_seconds Time since metrics collection started")
        lines.append("# TYPE psi_audit_uptime_seconds gauge")
        lines.append(f"psi_audit_uptime_seconds {metrics['uptime_seconds']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_urls_total Total number of URLs processed")
        lines.append("# TYPE psi_audit_urls_total counter")
        lines.append(f"psi_audit_urls_total{{status=\"total\"}} {metrics['total_urls']}")
        lines.append(f"psi_audit_urls_total{{status=\"success\"}} {metrics['successful_urls']}")
        lines.append(f"psi_audit_urls_total{{status=\"failed\"}} {metrics['failed_urls']}")
        lines.append(f"psi_audit_urls_total{{status=\"skipped\"}} {metrics['skipped_urls']}")
        lines.append("")
        
        lines.append("# HELP psi_audit_success_rate Success rate percentage")
        lines.append("# TYPE psi_audit_success_rate gauge")
        lines.append(f"psi_audit_success_rate {metrics['success_rate_percent']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_failure_rate Failure rate percentage")
        lines.append("# TYPE psi_audit_failure_rate gauge")
        lines.append(f"psi_audit_failure_rate {metrics['failure_rate_percent']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_cache_operations Cache operations")
        lines.append("# TYPE psi_audit_cache_operations counter")
        lines.append(f"psi_audit_cache_operations{{result=\"hit\"}} {metrics['cache_hits']}")
        lines.append(f"psi_audit_cache_operations{{result=\"miss\"}} {metrics['cache_misses']}")
        lines.append("")
        
        lines.append("# HELP psi_audit_cache_hit_ratio Cache hit ratio percentage")
        lines.append("# TYPE psi_audit_cache_hit_ratio gauge")
        lines.append(f"psi_audit_cache_hit_ratio {metrics['cache_hit_ratio_percent']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_api_calls_total Total API calls")
        lines.append("# TYPE psi_audit_api_calls_total counter")
        lines.append(f"psi_audit_api_calls_total{{api=\"sheets\"}} {metrics['api_calls_sheets']}")
        lines.append(f"psi_audit_api_calls_total{{api=\"cypress\"}} {metrics['api_calls_cypress']}")
        lines.append("")
        
        lines.append("# HELP psi_audit_processing_time_seconds Average processing time per URL")
        lines.append("# TYPE psi_audit_processing_time_seconds gauge")
        lines.append(f"psi_audit_processing_time_seconds {metrics['avg_processing_time_seconds']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_alert_active Whether failure rate alert is active")
        lines.append("# TYPE psi_audit_alert_active gauge")
        lines.append(f"psi_audit_alert_active {1 if metrics['alert_triggered'] else 0}")
        lines.append("")
        
        threading = metrics['threading']
        lines.append("# HELP psi_audit_threading_errors_total Threading-related errors")
        lines.append("# TYPE psi_audit_threading_errors_total counter")
        lines.append(f"psi_audit_threading_errors_total{{type=\"greenlet\"}} {threading['greenlet_errors']}")
        lines.append(f"psi_audit_threading_errors_total{{type=\"conflict\"}} {threading['thread_conflicts']}")
        lines.append(f"psi_audit_threading_errors_total{{type=\"event_loop_failure\"}} {threading['event_loop_failures']}")
        lines.append("")
        
        pw = metrics['playwright']
        lines.append("# HELP psi_audit_playwright_page_load_time_seconds Average page load time")
        lines.append("# TYPE psi_audit_playwright_page_load_time_seconds gauge")
        lines.append(f"psi_audit_playwright_page_load_time_seconds {pw['avg_page_load_time_seconds']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_playwright_browser_startup_time_seconds Average browser startup time")
        lines.append("# TYPE psi_audit_playwright_browser_startup_time_seconds gauge")
        lines.append(f"psi_audit_playwright_browser_startup_time_seconds {pw['avg_browser_startup_time_seconds']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_playwright_memory_usage_mb Browser memory usage statistics")
        lines.append("# TYPE psi_audit_playwright_memory_usage_mb gauge")
        lines.append(f"psi_audit_playwright_memory_usage_mb{{stat=\"avg\"}} {pw['avg_memory_usage_mb']:.2f}")
        lines.append(f"psi_audit_playwright_memory_usage_mb{{stat=\"max\"}} {pw['max_memory_usage_mb']:.2f}")
        lines.append(f"psi_audit_playwright_memory_usage_mb{{stat=\"min\"}} {pw['min_memory_usage_mb']:.2f}")
        lines.append(f"psi_audit_playwright_memory_usage_mb{{stat=\"avg_before_cleanup\"}} {pw['avg_memory_before_cleanup_mb']:.2f}")
        lines.append(f"psi_audit_playwright_memory_usage_mb{{stat=\"avg_after_cleanup\"}} {pw['avg_memory_after_cleanup_mb']:.2f}")
        lines.append(f"psi_audit_playwright_memory_usage_mb{{stat=\"avg_saved_cleanup\"}} {pw['avg_memory_saved_cleanup_mb']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_playwright_starts Browser instance starts")
        lines.append("# TYPE psi_audit_playwright_starts counter")
        lines.append(f"psi_audit_playwright_starts{{type=\"warm\"}} {pw['warm_starts']}")
        lines.append(f"psi_audit_playwright_starts{{type=\"cold\"}} {pw['cold_starts']}")
        lines.append("")
        
        lines.append("# HELP psi_audit_playwright_warm_start_ratio Warm start ratio percentage")
        lines.append("# TYPE psi_audit_playwright_warm_start_ratio gauge")
        lines.append(f"psi_audit_playwright_warm_start_ratio {pw['warm_start_ratio_percent']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_playwright_requests HTTP requests")
        lines.append("# TYPE psi_audit_playwright_requests counter")
        lines.append(f"psi_audit_playwright_requests{{status=\"total\"}} {pw['total_requests']}")
        lines.append(f"psi_audit_playwright_requests{{status=\"blocked\"}} {pw['blocked_requests']}")
        lines.append("")
        
        lines.append("# HELP psi_audit_playwright_blocking_ratio Request blocking ratio percentage")
        lines.append("# TYPE psi_audit_playwright_blocking_ratio gauge")
        lines.append(f"psi_audit_playwright_blocking_ratio {pw['blocking_ratio_percent']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_playwright_instance_refreshes Browser instance refreshes")
        lines.append("# TYPE psi_audit_playwright_instance_refreshes counter")
        lines.append(f"psi_audit_playwright_instance_refreshes {pw['instance_refreshes']}")
        lines.append("")
        
        inter_url = metrics['inter_url_delays']
        lines.append("# HELP psi_audit_inter_url_delay_seconds Inter-URL delay statistics")
        lines.append("# TYPE psi_audit_inter_url_delay_seconds gauge")
        lines.append(f"psi_audit_inter_url_delay_seconds{{stat=\"avg\"}} {inter_url['avg_delay_seconds']:.2f}")
        lines.append(f"psi_audit_inter_url_delay_seconds{{stat=\"total\"}} {inter_url['total_delay_seconds']:.2f}")
        lines.append("")
        
        lines.append("# HELP psi_audit_inter_url_delay_count Total inter-URL delays recorded")
        lines.append("# TYPE psi_audit_inter_url_delay_count counter")
        lines.append(f"psi_audit_inter_url_delay_count {inter_url['count']}")
        lines.append("")
        
        seq = metrics['sequential_processing']
        lines.append("# HELP psi_audit_sequential_processing_active Sequential processing active status")
        lines.append("# TYPE psi_audit_sequential_processing_active gauge")
        lines.append(f"psi_audit_sequential_processing_active {1 if seq['active'] else 0}")
        lines.append("")
        
        lines.append("# HELP psi_audit_sequential_urls_per_minute URLs processed per minute")
        lines.append("# TYPE psi_audit_sequential_urls_per_minute gauge")
        lines.append(f"psi_audit_sequential_urls_per_minute {seq['urls_per_minute']:.2f}")
        lines.append("")
        
        if seq['active']:
            lines.append("# HELP psi_audit_sequential_elapsed_time_seconds Sequential processing elapsed time")
            lines.append("# TYPE psi_audit_sequential_elapsed_time_seconds gauge")
            lines.append(f"psi_audit_sequential_elapsed_time_seconds {seq['elapsed_time_seconds']:.2f}")
            lines.append("")
            
            lines.append("# HELP psi_audit_sequential_urls_processed URLs processed in current session")
            lines.append("# TYPE psi_audit_sequential_urls_processed counter")
            lines.append(f"psi_audit_sequential_urls_processed {seq['urls_processed']}")
            lines.append("")
        
        for reason, count in metrics['failure_reasons'].items():
            lines.append(f"psi_audit_failures_by_reason{{reason=\"{reason}\"}} {count}")
        
        return "\n".join(lines)
    
    def export_json(self, indent: int = 2) -> str:
        """
        Export metrics as JSON.
        
        Args:
            indent: JSON indentation level
            
        Returns:
            JSON string
        """
        return json.dumps(self.get_metrics(), indent=indent)
    
    def save_prometheus_metrics(self, filepath: str = 'metrics.prom'):
        """Save Prometheus metrics to file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.export_prometheus())
    
    def save_json_metrics(self, filepath: str = 'metrics.json'):
        """Save JSON metrics to file"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.export_json())
    
    def get_recent_results(self, limit: int = 100) -> List[Dict]:
        """Get recent URL processing results"""
        with self._lock:
            return self._url_results[-limit:] if self._url_results else []
    
    def reset(self):
        """Reset all metrics"""
        with self._lock:
            self._start_time = time.time()
            self._total_urls = 0
            self._successful_urls = 0
            self._failed_urls = 0
            self._skipped_urls = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._api_calls_sheets = 0
            self._api_calls_cypress = 0
            self._processing_times.clear()
            self._failure_reasons.clear()
            self._url_results.clear()
            self._alert_triggered = False
            self._playwright_page_load_times.clear()
            self._playwright_browser_startup_times.clear()
            self._playwright_memory_usage.clear()
            self._playwright_warm_starts = 0
            self._playwright_cold_starts = 0
            self._playwright_total_requests = 0
            self._playwright_blocked_requests = 0
            self._playwright_blocked_by_type.clear()
            self._playwright_instance_refreshes = 0
            self._playwright_memory_before_cleanup.clear()
            self._playwright_memory_after_cleanup.clear()
            self._threading_greenlet_errors = 0
            self._threading_conflicts = 0
            self._threading_event_loop_failures = 0
            self._inter_url_delays.clear()
            self._sequential_processing_start = None
            self._sequential_urls_processed = 0
            self._sequential_last_url_time = None


_global_metrics_collector = None
_metrics_collector_lock = threading.Lock()


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector instance"""
    global _global_metrics_collector
    with _metrics_collector_lock:
        if _global_metrics_collector is None:
            _global_metrics_collector = MetricsCollector()
        return _global_metrics_collector


def reset_metrics_collector():
    """Reset global metrics collector"""
    global _global_metrics_collector
    with _metrics_collector_lock:
        if _global_metrics_collector is not None:
            _global_metrics_collector.reset()
