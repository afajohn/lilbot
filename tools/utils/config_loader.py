import yaml
import os
from typing import Dict, Any, Optional


class ConfigLoader:
    
    @staticmethod
    def load_config(config_file: str) -> Dict[str, Any]:
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        if not config:
            return {}
        
        return config
    
    @staticmethod
    def merge_config_with_args(config: Dict[str, Any], args: Any) -> Any:
        for key, value in config.items():
            arg_key = key.replace('-', '_')
            
            if hasattr(args, arg_key):
                current_value = getattr(args, arg_key)
                
                if current_value is None or (isinstance(current_value, (list, tuple)) and not current_value):
                    setattr(args, arg_key, value)
        
        return args
