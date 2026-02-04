from typing import List, Tuple, Dict, Set
from collections import defaultdict
from urllib.parse import urlparse, urlunparse
from tools.utils.logger import get_logger


def _normalize_url(url: str) -> str:
    """Simple URL normalization: lowercase scheme/host, remove trailing slash, strip fragment."""
    try:
        parsed = urlparse(url)
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip('/') if parsed.path else '',
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        return normalized
    except Exception:
        return url


class DataQualityChecker:
    
    def __init__(self):
        self.logger = get_logger()
    
    def check_duplicate_urls(
        self, 
        urls: List[Tuple[int, str, any, any, bool]]
    ) -> Tuple[bool, List[Dict]]:
        duplicates_found = []
        url_map = defaultdict(list)
        normalized_url_map = defaultdict(list)
        
        for row_index, url, _, _, _ in urls:
            url_map[url].append(row_index)
            
            try:
                normalized = _normalize_url(url)
                normalized_url_map[normalized].append((row_index, url))
            except Exception as e:
                self.logger.warning(f"Could not normalize URL at row {row_index}: {url} - {e}")
        
        for url, rows in url_map.items():
            if len(rows) > 1:
                duplicates_found.append({
                    'type': 'exact_duplicate',
                    'url': url,
                    'rows': rows,
                    'count': len(rows)
                })
        
        for normalized_url, entries in normalized_url_map.items():
            if len(entries) > 1:
                original_urls = [url for _, url in entries]
                if len(set(original_urls)) > 1:
                    rows = [row for row, _ in entries]
                    duplicates_found.append({
                        'type': 'normalized_duplicate',
                        'normalized_url': normalized_url,
                        'original_urls': original_urls,
                        'rows': rows,
                        'count': len(rows)
                    })
        
        has_duplicates = len(duplicates_found) > 0
        
        return has_duplicates, duplicates_found
    
    def check_missing_data(
        self, 
        urls: List[Tuple[int, str, any, any, bool]]
    ) -> Tuple[bool, List[Dict]]:
        missing_data_found = []
        
        for row_index, url, mobile_score, desktop_score, _ in urls:
            issues = []
            if not url or not url.strip():
                issues.append('missing_url')
            if mobile_score is None or mobile_score == '':
                issues.append('missing_mobile_score')
            if desktop_score is None or desktop_score == '':
                issues.append('missing_desktop_score')
            
            if issues:
                missing_data_found.append({
                    'row': row_index,
                    'url': url,
                    'issues': issues
                })
        
        has_missing = len(missing_data_found) > 0
        
        return has_missing, missing_data_found
    
    def check_invalid_scores(
        self, 
        urls: List[Tuple[int, str, any, any, bool]]
    ) -> Tuple[bool, List[Dict]]:
        invalid_scores_found = []
        
        for row_index, url, mobile_score, desktop_score, _ in urls:
            issues = []
            
            try:
                if mobile_score is not None and mobile_score != '':
                    mobile_val = int(mobile_score)
                    if mobile_val < 0 or mobile_val > 100:
                        issues.append(f'mobile_score_out_of_range: {mobile_val}')
            except (ValueError, TypeError):
                issues.append(f'mobile_score_invalid: {mobile_score}')
            
            try:
                if desktop_score is not None and desktop_score != '':
                    desktop_val = int(desktop_score)
                    if desktop_val < 0 or desktop_val > 100:
                        issues.append(f'desktop_score_out_of_range: {desktop_val}')
            except (ValueError, TypeError):
                issues.append(f'desktop_score_invalid: {desktop_score}')
            
            if issues:
                invalid_scores_found.append({
                    'row': row_index,
                    'url': url,
                    'issues': issues
                })
        
        has_invalid = len(invalid_scores_found) > 0
        
        return has_invalid, invalid_scores_found
