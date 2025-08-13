"""
Data storage module for saving auction data in various formats
"""
import os
import json
# import pandas as pd  # Optional dependency
from typing import List, Dict, Any
from datetime import datetime
from utils.logger import setup_logger
from config import OUTPUT_DIR, OUTPUT_FORMAT, OUTPUT_FILENAME


class DataStorage:
    """Handles data storage in multiple formats"""
    
    def __init__(self):
        self.logger = setup_logger(__name__)
        self.output_dir = OUTPUT_DIR
        self._ensure_output_directory()
        
    def _ensure_output_directory(self):
        """Ensure output directory exists"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            self.logger.info(f"Created output directory: {self.output_dir}")
            
    def save_data(self, data: List[Dict[str, Any]], filename_suffix: str = "") -> Dict[str, str]:
        """Save data in configured format(s)"""
        
        if not data:
            self.logger.warning("No data to save")
            return {}
            
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{OUTPUT_FILENAME}_{timestamp}"
        
        if filename_suffix:
            base_filename += f"_{filename_suffix}"
            
        saved_files = {}
        
        try:
            # Save in requested format(s)
            if OUTPUT_FORMAT in ["csv", "both"]:
                csv_file = self._save_as_csv(data, base_filename)
                if csv_file:
                    saved_files['csv'] = csv_file
                    
            if OUTPUT_FORMAT in ["json", "both"]:
                json_file = self._save_as_json(data, base_filename)
                if json_file:
                    saved_files['json'] = json_file
                    
            # Save summary statistics
            summary_file = self._save_summary(data, base_filename)
            if summary_file:
                saved_files['summary'] = summary_file
                
            self.logger.info(f"Successfully saved {len(data)} records to {len(saved_files)} files")
            
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")
            
        return saved_files
        
    def _save_as_csv(self, data: List[Dict[str, Any]], base_filename: str) -> str:
        """Save data as CSV file"""
        try:
            import csv
            
            csv_filename = os.path.join(self.output_dir, f"{base_filename}.csv")
            
            if not data:
                return csv_filename
                
            # Get all possible field names
            all_fields = set()
            for item in data:
                all_fields.update(item.keys())
            all_fields = sorted(all_fields)
            
            # Write CSV file
            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=all_fields)
                writer.writeheader()
                
                for item in data:
                    # Flatten nested data
                    flattened_item = {}
                    for key, value in item.items():
                        if isinstance(value, (dict, list)):
                            flattened_item[key] = json.dumps(value, ensure_ascii=False)
                        else:
                            flattened_item[key] = value
                    writer.writerow(flattened_item)
            
            self.logger.info(f"Saved CSV file: {csv_filename}")
            return csv_filename
            
        except Exception as e:
            self.logger.error(f"Failed to save CSV file: {e}")
            return None
            
    def _save_as_json(self, data: List[Dict[str, Any]], base_filename: str) -> str:
        """Save data as JSON file"""
        try:
            json_filename = os.path.join(self.output_dir, f"{base_filename}.json")
            
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                
            self.logger.info(f"Saved JSON file: {json_filename}")
            return json_filename
            
        except Exception as e:
            self.logger.error(f"Failed to save JSON file: {e}")
            return None
            
    def _save_summary(self, data: List[Dict[str, Any]], base_filename: str) -> str:
        """Save summary statistics"""
        try:
            summary_filename = os.path.join(self.output_dir, f"{base_filename}_summary.txt")
            
            # Calculate statistics
            total_items = len(data)
            pages_crawled = len(set(item.get('page_number', 0) for item in data))
            
            # Get field statistics
            field_stats = {}
            for item in data:
                for field, value in item.items():
                    if field not in field_stats:
                        field_stats[field] = {'count': 0, 'non_empty': 0}
                    field_stats[field]['count'] += 1
                    if value and str(value).strip():
                        field_stats[field]['non_empty'] += 1
                        
            # Get jurisdiction statistics if available
            jurisdictions = {}
            for item in data:
                jurisdiction = item.get('jurisdiction', 'Unknown')
                jurisdictions[jurisdiction] = jurisdictions.get(jurisdiction, 0) + 1
                
            # Write summary
            with open(summary_filename, 'w', encoding='utf-8') as f:
                f.write(f"Bankruptcy Auction Crawl Summary\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*50}\n\n")
                
                f.write(f"Total Items: {total_items}\n")
                f.write(f"Pages Crawled: {pages_crawled}\n")
                f.write(f"Average Items per Page: {total_items/pages_crawled if pages_crawled > 0 else 0:.2f}\n\n")
                
                f.write(f"Field Statistics:\n")
                f.write(f"{'Field':<25} {'Total':<8} {'Non-Empty':<12} {'Fill Rate':<10}\n")
                f.write(f"{'-'*55}\n")
                for field, stats in field_stats.items():
                    fill_rate = (stats['non_empty'] / stats['count']) * 100 if stats['count'] > 0 else 0
                    f.write(f"{field:<25} {stats['count']:<8} {stats['non_empty']:<12} {fill_rate:<10.1f}%\n")
                    
                if jurisdictions:
                    f.write(f"\nJurisdiction Distribution:\n")
                    f.write(f"{'Jurisdiction':<30} {'Count':<8} {'Percentage':<10}\n")
                    f.write(f"{'-'*48}\n")
                    for jurisdiction, count in sorted(jurisdictions.items(), key=lambda x: x[1], reverse=True):
                        percentage = (count / total_items) * 100
                        f.write(f"{jurisdiction:<30} {count:<8} {percentage:<10.1f}%\n")
                        
            self.logger.info(f"Saved summary file: {summary_filename}")
            return summary_filename
            
        except Exception as e:
            self.logger.error(f"Failed to save summary file: {e}")
            return None
            
    def _flatten_nested_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Flatten nested data structures for CSV export"""
        try:
            flattened = {}
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    flattened[key] = json.dumps(value, ensure_ascii=False)
                else:
                    flattened[key] = value
            return flattened
            
        except Exception as e:
            self.logger.error(f"Error flattening nested data: {e}")
            return data
            
    def append_data(self, new_data: List[Dict[str, Any]], existing_file: str) -> bool:
        """Append new data to existing file"""
        try:
            if not os.path.exists(existing_file):
                self.logger.warning(f"Existing file not found: {existing_file}")
                return False
                
            file_ext = os.path.splitext(existing_file)[1].lower()
            
            if file_ext == '.csv':
                return self._append_to_csv(new_data, existing_file)
            elif file_ext == '.json':
                return self._append_to_json(new_data, existing_file)
            else:
                self.logger.error(f"Unsupported file format for append: {file_ext}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error appending data: {e}")
            return False
            
    def _append_to_csv(self, new_data: List[Dict[str, Any]], csv_file: str) -> bool:
        """Append data to existing CSV file"""
        try:
            import csv
            
            if not new_data:
                return True
                
            # Read existing headers
            existing_fields = []
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                existing_fields = next(reader, [])
                
            # Get all fields from new data
            all_fields = set(existing_fields)
            for item in new_data:
                all_fields.update(item.keys())
            all_fields = sorted(all_fields)
            
            # If fields are different, we need to rewrite the entire file
            if set(existing_fields) != set(all_fields):
                self.logger.warning("Field mismatch detected, this simple append won't work properly")
            
            # Append new data
            with open(csv_file, 'a', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=existing_fields)
                
                for item in new_data:
                    flattened_item = self._flatten_nested_data(item)
                    # Only write fields that exist in the original CSV
                    filtered_item = {k: flattened_item.get(k, '') for k in existing_fields}
                    writer.writerow(filtered_item)
            
            self.logger.info(f"Appended {len(new_data)} records to {csv_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to append to CSV: {e}")
            return False
            
    def _append_to_json(self, new_data: List[Dict[str, Any]], json_file: str) -> bool:
        """Append data to existing JSON file"""
        try:
            # Read existing data
            with open(json_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                
            # Append new data
            if isinstance(existing_data, list):
                existing_data.extend(new_data)
            else:
                existing_data = [existing_data] + new_data
                
            # Write back to file
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2, default=str)
                
            self.logger.info(f"Appended {len(new_data)} records to {json_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to append to JSON: {e}")
            return False