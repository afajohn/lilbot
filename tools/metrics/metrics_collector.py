import threading
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json


class MetricsCollector:
    """
    Collects and exports metrics in Prometheus-compatible format.
    Tracks success/failure rates, processing time, API quota usage, and cache hit ratio.
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
                'alert_triggered': self._alert_triggered
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
