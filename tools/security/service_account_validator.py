import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from tools.utils.exceptions import PermanentError
from tools.utils.logger import get_logger


class ServiceAccountValidator:
    REQUIRED_FIELDS = [
        'type',
        'project_id',
        'private_key_id',
        'private_key',
        'client_email',
        'client_id',
        'auth_uri',
        'token_uri'
    ]
    
    EXPIRATION_WARNING_DAYS = 30
    
    @staticmethod
    def validate(service_account_file: str) -> Tuple[bool, List[str]]:
        logger = get_logger()
        errors = []
        
        if not os.path.exists(service_account_file):
            errors.append(f"Service account file not found: {service_account_file}")
            return False, errors
        
        try:
            with open(service_account_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON format: {e}")
            return False, errors
        except Exception as e:
            errors.append(f"Failed to read service account file: {e}")
            return False, errors
        
        for field in ServiceAccountValidator.REQUIRED_FIELDS:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        if 'type' in data and data['type'] != 'service_account':
            errors.append(f"Invalid account type: expected 'service_account', got '{data['type']}'")
        
        if 'private_key' in data:
            private_key = data['private_key']
            if not private_key.startswith('-----BEGIN PRIVATE KEY-----'):
                errors.append("Invalid private key format: missing header")
            if not private_key.rstrip().endswith('-----END PRIVATE KEY-----'):
                errors.append("Invalid private key format: missing footer")
        
        if 'client_email' in data:
            client_email = data['client_email']
            if '@' not in client_email or not client_email.endswith('.iam.gserviceaccount.com'):
                errors.append(f"Invalid service account email format: {client_email}")
        
        warnings = ServiceAccountValidator._check_permissions(data)
        if warnings:
            for warning in warnings:
                logger.warning(f"Service account validation warning: {warning}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _check_permissions(data: Dict) -> List[str]:
        warnings = []
        
        if 'client_email' in data:
            logger = get_logger()
            logger.info(f"Service account email: {data['client_email']}")
            logger.info("Ensure this account has been granted Sheets API access")
        
        return warnings
