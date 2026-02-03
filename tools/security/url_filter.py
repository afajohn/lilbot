import re
from typing import List, Optional, Set
from urllib.parse import urlparse
from tools.utils.logger import get_logger


class URLFilter:
    
    def __init__(self, whitelist: Optional[List[str]] = None, blacklist: Optional[List[str]] = None):
        self.whitelist_patterns = self._compile_patterns(whitelist) if whitelist else None
        self.blacklist_patterns = self._compile_patterns(blacklist) if blacklist else []
        self.logger = get_logger()
        
        if self.whitelist_patterns:
            self.logger.info(f"URL whitelist enabled with {len(self.whitelist_patterns)} patterns")
        if self.blacklist_patterns:
            self.logger.info(f"URL blacklist enabled with {len(self.blacklist_patterns)} patterns")
    
    @staticmethod
    def _compile_patterns(patterns: List[str]) -> List[re.Pattern]:
        compiled = []
        for pattern in patterns:
            pattern = pattern.replace('.', r'\.')
            pattern = pattern.replace('*', '.*')
            pattern = f'^{pattern}$'
            compiled.append(re.compile(pattern, re.IGNORECASE))
        return compiled
    
    def is_allowed(self, url: str) -> bool:
        if self.whitelist_patterns:
            allowed = any(pattern.match(url) for pattern in self.whitelist_patterns)
            if not allowed:
                self.logger.warning(f"URL rejected by whitelist: {url}")
                return False
        
        if self.blacklist_patterns:
            blocked = any(pattern.match(url) for pattern in self.blacklist_patterns)
            if blocked:
                self.logger.warning(f"URL rejected by blacklist: {url}")
                return False
        
        return True
    
    @staticmethod
    def sanitize_url(url: str) -> str:
        url = url.strip()
        
        if not url:
            raise ValueError("URL cannot be empty")
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")
        
        if not parsed.scheme in ('http', 'https'):
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
        
        if not parsed.netloc:
            raise ValueError("URL must have a valid domain")
        
        dangerous_chars = ['<', '>', '"', "'", '`', '{', '}', '|', '\\', '^', '[', ']']
        for char in dangerous_chars:
            if char in url:
                raise ValueError(f"URL contains dangerous character: {char}")
        
        return url
