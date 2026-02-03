import hashlib
import json
import os
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from threading import Lock

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from tools.utils.logger import get_logger


class CacheBackend:
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError
    
    def set(self, key: str, value: Dict[str, Any], ttl: int) -> bool:
        raise NotImplementedError
    
    def delete(self, key: str) -> bool:
        raise NotImplementedError
    
    def clear(self) -> bool:
        raise NotImplementedError
    
    def exists(self, key: str) -> bool:
        raise NotImplementedError


class RedisBackend(CacheBackend):
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0, 
                 password: Optional[str] = None, key_prefix: str = 'psi:'):
        self.key_prefix = key_prefix
        self.logger = get_logger()
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            self.client.ping()
            self.logger.info(f"Connected to Redis at {host}:{port}")
        except Exception as e:
            self.logger.warning(f"Failed to connect to Redis: {e}")
            raise
    
    def _make_key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            data = self.client.get(self._make_key(key))
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            self.logger.warning(f"Redis get error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Dict[str, Any], ttl: int) -> bool:
        try:
            self.client.setex(
                self._make_key(key),
                ttl,
                json.dumps(value)
            )
            return True
        except Exception as e:
            self.logger.warning(f"Redis set error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        try:
            self.client.delete(self._make_key(key))
            return True
        except Exception as e:
            self.logger.warning(f"Redis delete error for key {key}: {e}")
            return False
    
    def clear(self) -> bool:
        try:
            pattern = self._make_key('*')
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as e:
            self.logger.warning(f"Redis clear error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        try:
            return bool(self.client.exists(self._make_key(key)))
        except Exception as e:
            self.logger.warning(f"Redis exists error for key {key}: {e}")
            return False


class FileCacheBackend(CacheBackend):
    def __init__(self, cache_dir: str = '.cache', max_entries: int = 1000):
        self.cache_dir = cache_dir
        self.max_entries = max_entries
        self.logger = get_logger()
        self._lock = Lock()
        self._lru_order = OrderedDict()
        
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self._load_lru_index()
        self.logger.info(f"Initialized file cache at {cache_dir} with max {max_entries} entries")
    
    def _get_cache_file_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def _get_index_file_path(self) -> str:
        return os.path.join(self.cache_dir, '_cache_index.json')
    
    def _load_lru_index(self):
        index_file = self._get_index_file_path()
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                    for key in index_data.get('lru_order', []):
                        self._lru_order[key] = None
            except Exception as e:
                self.logger.warning(f"Failed to load LRU index: {e}")
                self._lru_order = OrderedDict()
    
    def _save_lru_index(self):
        index_file = self._get_index_file_path()
        try:
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'lru_order': list(self._lru_order.keys()),
                    'last_updated': datetime.utcnow().isoformat()
                }, f)
        except Exception as e:
            self.logger.warning(f"Failed to save LRU index: {e}")
    
    def _evict_oldest(self):
        if len(self._lru_order) >= self.max_entries:
            oldest_key = next(iter(self._lru_order))
            self._lru_order.pop(oldest_key, None)
            cache_file = self._get_cache_file_path(oldest_key)
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                self.logger.debug(f"Evicted oldest cache entry: {oldest_key}")
            except Exception as e:
                self.logger.warning(f"Failed to evict cache file {cache_file}: {e}")
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cache_file = self._get_cache_file_path(key)
            
            if not os.path.exists(cache_file):
                return None
            
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                expiry_time = datetime.fromisoformat(data.get('expiry'))
                if datetime.utcnow() > expiry_time:
                    os.remove(cache_file)
                    self._lru_order.pop(key, None)
                    self._save_lru_index()
                    return None
                
                self._lru_order.move_to_end(key)
                self._save_lru_index()
                
                return data.get('value')
                
            except Exception as e:
                self.logger.warning(f"Failed to read cache file {cache_file}: {e}")
                return None
    
    def set(self, key: str, value: Dict[str, Any], ttl: int) -> bool:
        with self._lock:
            self._evict_oldest()
            
            cache_file = self._get_cache_file_path(key)
            expiry_time = datetime.utcnow() + timedelta(seconds=ttl)
            
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'value': value,
                        'expiry': expiry_time.isoformat(),
                        'created_at': datetime.utcnow().isoformat()
                    }, f, indent=2)
                
                self._lru_order[key] = None
                self._lru_order.move_to_end(key)
                self._save_lru_index()
                
                return True
                
            except Exception as e:
                self.logger.warning(f"Failed to write cache file {cache_file}: {e}")
                return False
    
    def delete(self, key: str) -> bool:
        with self._lock:
            cache_file = self._get_cache_file_path(key)
            
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                self._lru_order.pop(key, None)
                self._save_lru_index()
                return True
            except Exception as e:
                self.logger.warning(f"Failed to delete cache file {cache_file}: {e}")
                return False
    
    def clear(self) -> bool:
        with self._lock:
            try:
                for key in list(self._lru_order.keys()):
                    cache_file = self._get_cache_file_path(key)
                    if os.path.exists(cache_file):
                        os.remove(cache_file)
                
                self._lru_order.clear()
                self._save_lru_index()
                
                return True
            except Exception as e:
                self.logger.warning(f"Failed to clear cache: {e}")
                return False
    
    def exists(self, key: str) -> bool:
        with self._lock:
            cache_file = self._get_cache_file_path(key)
            
            if not os.path.exists(cache_file):
                return False
            
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                expiry_time = datetime.fromisoformat(data.get('expiry'))
                if datetime.utcnow() > expiry_time:
                    os.remove(cache_file)
                    self._lru_order.pop(key, None)
                    self._save_lru_index()
                    return False
                
                return True
                
            except Exception as e:
                self.logger.warning(f"Failed to check cache file {cache_file}: {e}")
                return False


class CacheManager:
    DEFAULT_TTL = 86400
    
    def __init__(self, backend: Optional[CacheBackend] = None, enabled: bool = True):
        self.logger = get_logger()
        self.enabled = enabled
        
        if not enabled:
            self.logger.info("Cache is disabled")
            self.backend = None
            return
        
        if backend:
            self.backend = backend
        else:
            self.backend = self._initialize_default_backend()
    
    def _initialize_default_backend(self) -> CacheBackend:
        redis_host = os.environ.get('REDIS_HOST', 'localhost')
        redis_port = int(os.environ.get('REDIS_PORT', '6379'))
        redis_db = int(os.environ.get('REDIS_DB', '0'))
        redis_password = os.environ.get('REDIS_PASSWORD')
        
        if REDIS_AVAILABLE:
            try:
                return RedisBackend(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password
                )
            except Exception as e:
                self.logger.warning(f"Redis backend failed, falling back to file cache: {e}")
        else:
            self.logger.info("Redis not available, using file cache backend")
        
        cache_dir = os.environ.get('CACHE_DIR', '.cache')
        max_entries = int(os.environ.get('CACHE_MAX_ENTRIES', '1000'))
        return FileCacheBackend(cache_dir=cache_dir, max_entries=max_entries)
    
    def _generate_cache_key(self, url: str, timestamp_day: Optional[str] = None) -> str:
        if timestamp_day is None:
            timestamp_day = datetime.utcnow().strftime('%Y-%m-%d')
        
        fingerprint = f"{url}|{timestamp_day}"
        hash_obj = hashlib.sha256(fingerprint.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def get(self, url: str) -> Optional[Dict[str, Any]]:
        if not self.enabled or not self.backend:
            return None
        
        cache_key = self._generate_cache_key(url)
        result = self.backend.get(cache_key)
        
        if result:
            self.logger.debug(f"Cache HIT for URL: {url}")
        else:
            self.logger.debug(f"Cache MISS for URL: {url}")
        
        return result
    
    def set(self, url: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        if not self.enabled or not self.backend:
            return False
        
        if ttl is None:
            ttl = self.DEFAULT_TTL
        
        cache_key = self._generate_cache_key(url)
        
        cache_data = {
            'url': url,
            'mobile_score': value.get('mobile_score'),
            'desktop_score': value.get('desktop_score'),
            'mobile_psi_url': value.get('mobile_psi_url'),
            'desktop_psi_url': value.get('desktop_psi_url'),
            'cached_at': datetime.utcnow().isoformat(),
            'timestamp_day': datetime.utcnow().strftime('%Y-%m-%d')
        }
        
        result = self.backend.set(cache_key, cache_data, ttl)
        
        if result:
            self.logger.debug(f"Cache SET for URL: {url} (TTL: {ttl}s)")
        else:
            self.logger.warning(f"Failed to cache result for URL: {url}")
        
        return result
    
    def invalidate(self, url: str) -> bool:
        if not self.enabled or not self.backend:
            return False
        
        cache_key = self._generate_cache_key(url)
        result = self.backend.delete(cache_key)
        
        if result:
            self.logger.info(f"Cache invalidated for URL: {url}")
        
        return result
    
    def invalidate_all(self) -> bool:
        if not self.enabled or not self.backend:
            return False
        
        result = self.backend.clear()
        
        if result:
            self.logger.info("All cache entries invalidated")
        
        return result
    
    def exists(self, url: str) -> bool:
        if not self.enabled or not self.backend:
            return False
        
        cache_key = self._generate_cache_key(url)
        return self.backend.exists(cache_key)


_global_cache_manager = None
_cache_manager_lock = Lock()


def get_cache_manager(enabled: bool = True) -> CacheManager:
    global _global_cache_manager
    with _cache_manager_lock:
        if _global_cache_manager is None:
            _global_cache_manager = CacheManager(enabled=enabled)
        return _global_cache_manager


def reset_cache_manager():
    global _global_cache_manager
    with _cache_manager_lock:
        _global_cache_manager = None
