import json
import csv
from typing import List, Dict, Any


class ResultExporter:
    
    @staticmethod
    def export_to_json(results: List[Dict[str, Any]], output_file: str) -> None:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def export_to_csv(results: List[Dict[str, Any]], output_file: str) -> None:
        if not results:
            return
        
        fieldnames = set()
        for result in results:
            fieldnames.update(result.keys())
        
        fieldnames = sorted(fieldnames)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                flattened = {}
                for key, value in result.items():
                    if isinstance(value, (dict, list)):
                        flattened[key] = json.dumps(value)
                    else:
                        flattened[key] = value
                writer.writerow(flattened)
