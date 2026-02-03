from typing import List, Tuple, Dict, Set
from collections import defaultdict
from tools.utils.logger import get_logger
from tools.utils.url_validator import URLNormalizer


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
                normalized = URLNormalizer.normalize_url(url)
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
    
    def report_duplicates(self, duplicates: List[Dict]) -> None:
        if not duplicates:
            self.logger.info("No duplicate URLs found")
            return
        
        self.logger.warning("=" * 80)
        self.logger.warning(f"DUPLICATE URLS DETECTED: {len(duplicates)} duplicate groups found")
        self.logger.warning("=" * 80)
        
        exact_count = sum(1 for d in duplicates if d['type'] == 'exact_duplicate')
        normalized_count = sum(1 for d in duplicates if d['type'] == 'normalized_duplicate')
        
        if exact_count > 0:
            self.logger.warning(f"\nExact Duplicates: {exact_count}")
            for dup in duplicates:
                if dup['type'] == 'exact_duplicate':
                    self.logger.warning(f"  URL: {dup['url']}")
                    self.logger.warning(f"  Rows: {', '.join(map(str, dup['rows']))}")
                    self.logger.warning(f"  Count: {dup['count']}")
                    self.logger.warning("")
        
        if normalized_count > 0:
            self.logger.warning(f"\nNormalized Duplicates (same URL with minor variations): {normalized_count}")
            for dup in duplicates:
                if dup['type'] == 'normalized_duplicate':
                    self.logger.warning(f"  Normalized URL: {dup['normalized_url']}")
                    self.logger.warning(f"  Original URLs:")
                    for i, url in enumerate(dup['original_urls']):
                        self.logger.warning(f"    - Row {dup['rows'][i]}: {url}")
                    self.logger.warning("")
        
        self.logger.warning("=" * 80)
    
    def check_empty_urls(self, urls: List[Tuple[int, str, any, any, bool]]) -> Tuple[bool, List[int]]:
        empty_rows = []
        
        for row_index, url, _, _, _ in urls:
            if not url or not url.strip():
                empty_rows.append(row_index)
        
        if empty_rows:
            self.logger.warning(f"Empty URLs found at rows: {', '.join(map(str, empty_rows))}")
        
        return len(empty_rows) > 0, empty_rows
    
    def perform_quality_checks(
        self, 
        urls: List[Tuple[int, str, any, any, bool]]
    ) -> Dict:
        self.logger.info("Performing data quality checks...")
        
        results = {
            'has_issues': False,
            'duplicates': [],
            'empty_urls': [],
            'total_urls': len(urls)
        }
        
        has_duplicates, duplicates = self.check_duplicate_urls(urls)
        if has_duplicates:
            results['has_issues'] = True
            results['duplicates'] = duplicates
            self.report_duplicates(duplicates)
        
        has_empty, empty_rows = self.check_empty_urls(urls)
        if has_empty:
            results['has_issues'] = True
            results['empty_urls'] = empty_rows
        
        if not results['has_issues']:
            self.logger.info("Data quality checks passed: no issues found")
        
        return results
