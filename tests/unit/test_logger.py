import pytest
import os
import sys
import logging
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools'))

from utils import logger


class TestSetupLogger:
    def test_setup_logger_creates_logger(self, tmp_path):
        logger._logger_lock = __import__('threading').Lock()
        
        log_dir = str(tmp_path / "logs")
        log = logger.setup_logger(name='test_logger', log_dir=log_dir)
        
        assert log is not None
        assert log.name == 'test_logger'
        assert log.level == logging.INFO
        assert os.path.exists(log_dir)
        assert len(log.handlers) >= 2
        
        logging.getLogger('test_logger').handlers.clear()
    
    def test_setup_logger_returns_existing_logger(self, tmp_path):
        log_dir = str(tmp_path / "logs")
        
        log1 = logger.setup_logger(name='test_logger2', log_dir=log_dir)
        log2 = logger.setup_logger(name='test_logger2', log_dir=log_dir)
        
        assert log1 is log2
        assert len(log1.handlers) == len(log2.handlers)
        
        logging.getLogger('test_logger2').handlers.clear()
    
    def test_setup_logger_creates_file_handler(self, tmp_path):
        log_dir = str(tmp_path / "logs")
        log = logger.setup_logger(name='test_logger3', log_dir=log_dir)
        
        file_handlers = [h for h in log.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 1
        
        file_handler = file_handlers[0]
        assert 'audit_' in file_handler.baseFilename
        assert file_handler.baseFilename.endswith('.log')
        
        logging.getLogger('test_logger3').handlers.clear()
    
    def test_setup_logger_creates_console_handler(self, tmp_path):
        log_dir = str(tmp_path / "logs")
        log = logger.setup_logger(name='test_logger4', log_dir=log_dir)
        
        console_handlers = [h for h in log.handlers if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)]
        assert len(console_handlers) >= 1
        
        logging.getLogger('test_logger4').handlers.clear()
    
    def test_setup_logger_thread_safe(self, tmp_path):
        import threading
        
        log_dir = str(tmp_path / "logs")
        results = []
        
        def setup_in_thread():
            log = logger.setup_logger(name='test_logger_thread', log_dir=log_dir)
            results.append(log)
        
        threads = [threading.Thread(target=setup_in_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert all(r is results[0] for r in results)
        
        logging.getLogger('test_logger_thread').handlers.clear()


class TestGetLogger:
    def test_get_logger_returns_logger(self):
        test_logger = logging.getLogger('test_get_logger')
        
        result = logger.get_logger('test_get_logger')
        
        assert result is test_logger
    
    def test_get_logger_default_name(self):
        result = logger.get_logger()
        
        assert result.name == 'audit'


class TestLoggerIntegration:
    def test_logger_writes_to_file(self, tmp_path):
        log_dir = str(tmp_path / "logs")
        log = logger.setup_logger(name='test_file_write', log_dir=log_dir)
        
        log.info("Test message")
        
        log_files = os.listdir(log_dir)
        assert len(log_files) > 0
        
        log_file_path = os.path.join(log_dir, log_files[0])
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "Test message" in content
        
        logging.getLogger('test_file_write').handlers.clear()
    
    def test_logger_formats_messages_correctly(self, tmp_path):
        log_dir = str(tmp_path / "logs")
        log = logger.setup_logger(name='test_format', log_dir=log_dir)
        
        log.info("Test info message")
        log.error("Test error message")
        
        log_files = os.listdir(log_dir)
        log_file_path = os.path.join(log_dir, log_files[0])
        
        with open(log_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "INFO" in content
        assert "ERROR" in content
        assert "test_format" in content
        
        logging.getLogger('test_format').handlers.clear()
