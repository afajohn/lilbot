import re
import socket
from typing import Tuple, Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import urllib.request
import urllib.error
from tools.utils.logger import get_logger


class URLValidator:
    
    URL_REGEX = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    def __init__(self, dns_timeout: float = 5.0, redirect_timeout: float = 10.0):
        self.dns_timeout = dns_timeout
        self.redirect_timeout = redirect_timeout
        self.logger = get_logger()
    
    def validate_url_format(self, url: str) -> Tuple[bool, Optional[str]]:
        if not url or not url.strip():
            return False, "URL is empty"
        
        url = url.strip()
        
        if not self.URL_REGEX.match(url):
            return False, "URL format is invalid"
        
        try:
            parsed = urlparse(url)
            if not parsed.scheme:
                return False, "URL missing scheme (http/https)"
            if not parsed.netloc:
                return False, "URL missing domain/host"
        except Exception as e:
            return False, f"URL parsing failed: {e}"
        
        return True, None
    
    def validate_dns(self, url: str) -> Tuple[bool, Optional[str]]:
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            
            if not hostname:
                return False, "Cannot extract hostname from URL"
            
            socket.setdefaulttimeout(self.dns_timeout)
            socket.gethostbyname(hostname)
            return True, None
            
        except socket.gaierror as e:
            return False, f"DNS resolution failed: {e}"
        except socket.timeout:
            return False, "DNS resolution timed out"
        except Exception as e:
            return False, f"DNS validation error: {e}"
    
    def check_redirect_chain(self, url: str, max_redirects: int = 3) -> Tuple[bool, int, Optional[str]]:
        try:
            class RedirectHandler(urllib.request.HTTPRedirectHandler):
                redirect_count = 0
                
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    self.redirect_count += 1
                    return urllib.request.HTTPRedirectHandler.redirect_request(
                        self, req, fp, code, msg, headers, newurl
                    )
            
            handler = RedirectHandler()
            opener = urllib.request.build_opener(handler)
            
            request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            
            try:
                opener.open(request, timeout=self.redirect_timeout)
            except urllib.error.URLError:
                pass
            
            redirect_count = handler.redirect_count
            
            if redirect_count > max_redirects:
                return False, redirect_count, f"Too many redirects ({redirect_count} > {max_redirects})"
            
            return True, redirect_count, None
            
        except Exception as e:
            return True, 0, f"Could not check redirects: {e}"
    
    def validate_url(self, url: str, check_dns: bool = True, check_redirects: bool = True) -> Tuple[bool, dict]:
        results = {
            'url': url,
            'format_valid': False,
            'dns_valid': None,
            'redirect_count': None,
            'redirect_ok': None,
            'errors': []
        }
        
        format_valid, format_error = self.validate_url_format(url)
        results['format_valid'] = format_valid
        if format_error:
            results['errors'].append(format_error)
            return False, results
        
        if check_dns:
            dns_valid, dns_error = self.validate_dns(url)
            results['dns_valid'] = dns_valid
            if dns_error:
                results['errors'].append(dns_error)
        
        if check_redirects:
            redirect_ok, redirect_count, redirect_error = self.check_redirect_chain(url)
            results['redirect_ok'] = redirect_ok
            results['redirect_count'] = redirect_count
            if redirect_error:
                results['errors'].append(redirect_error)
        
        is_valid = results['format_valid'] and (results['dns_valid'] is not False) and (results['redirect_ok'] is not False)
        
        return is_valid, results


class URLNormalizer:
    
    @staticmethod
    def normalize_url(url: str, remove_trailing_slash: bool = True, sort_query_params: bool = True) -> str:
        parsed = urlparse(url.strip())
        
        scheme = parsed.scheme.lower() if parsed.scheme else 'https'
        netloc = parsed.netloc.lower()
        path = parsed.path
        
        if remove_trailing_slash and path != '/':
            path = path.rstrip('/')
        
        query = parsed.query
        if sort_query_params and query:
            params = parse_qs(query, keep_blank_values=True)
            sorted_params = sorted(params.items())
            query = urlencode(sorted_params, doseq=True)
        
        fragment = parsed.fragment
        
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
        
        return normalized
    
    @staticmethod
    def urls_are_equivalent(url1: str, url2: str) -> bool:
        normalized1 = URLNormalizer.normalize_url(url1)
        normalized2 = URLNormalizer.normalize_url(url2)
        return normalized1 == normalized2
