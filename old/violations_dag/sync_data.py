# /sync_data.py
import sys
import json
import time
import requests
import oracledb
import concurrent.futures
from datetime import datetime, timezone
from dateutil.parser import parse as date_parse
from tqdm import tqdm
from typing import Dict, Any, List, Optional, Tuple

# Import shared modules
from common import config
from common.logging_setup import setup_logging
from common.db_connector import DatabaseConnector
from common.attribute_mapper import ATTRIBUTE_MAPPER


# Setup logger for this script
logger = setup_logging(config.LOG_FILE_SYNC)


# --- Constants ---
SYNC_STATE_FILE = "sync_state.json"
PRE_FLIGHT_TIMEOUT_SECONDS = 60
PRE_FLIGHT_RETRY_DELAY = 5

class SyncManager:
    """Manages the entire data synchronization process with robustness and detailed statistics."""

    def __init__(self):
        self.stats = self._reset_stats()

    def _reset_stats(self) -> Dict[str, Any]:
        """Returns a clean dictionary for tracking detailed statistics."""
        return {

            "db_records_read": 0,
            "invalid_rows_skipped": 0,
            "records_added": 0,
            "records_updated": 0,
            "records_deleted": 0,
            "push_success": 0,
            "push_failed": 0,
            "delete_success": 0,
            "delete_failed": 0,
            "api_chunks_success_first_try": 0,
            "api_chunks_success_retries": 0,
            "api_chunks_failed": 0,
            "total_api_retries": 0,
            "final_record_count": 0,
            
        }

    def _load_state(self) -> Tuple[str, List[str]]:
        try:
            with open(SYNC_STATE_FILE, 'r') as f:
                state = json.load(f)

                timestamp = state.get("last_successful_sync_timestamp")

                ids = state.get("last_known_object_ids", [])
                
                logger.info(f"Loaded sync state. Last sync at: {timestamp}")
                
                return timestamp, ids
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("Sync state file not found or invalid. Assuming initial sync.")
            
            return "1970-01-01T00:00:00.000000+00:00", []

    def _save_state(self, timestamp: datetime, all_ids: List[str]):
        iso_timestamp = timestamp.isoformat()
        
        state = {"last_successful_sync_timestamp": iso_timestamp, "last_known_object_ids": all_ids}
        
        with open(SYNC_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Successfully saved new sync state. Timestamp: {iso_timestamp}")

    def _row_to_feature(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Converts a database row dictionary to a GeoJSON Feature, with validation."""
        properties = {}
        
        row_upper_keys = {k.upper(): v for k, v in row.items()}

        for db_col, map_info in ATTRIBUTE_MAPPER.items():
            if db_col.upper() in row_upper_keys:
                value = row_upper_keys[db_col.upper()]
                
                if map_info["type"] == "date_time" and value is not None:
                    try:
                        dt_obj = date_parse(value, dayfirst=True) if isinstance(value, str) else value
                        
                        properties[db_col] = dt_obj.isoformat()
                    except (ValueError, TypeError):
                        properties[db_col] = None
                else:
                    properties[db_col] = value

        primary_name_col_upper = config.ASSET_PRIMARY_NAME_COLUMN.upper()
        
        if primary_name_col_upper in row_upper_keys:
            properties[f"{config.ASSET_PRIMARY_NAME_COLUMN}_ns"] = str(row_upper_keys[primary_name_col_upper])

        lon = row_upper_keys.get('LONGITUDE')
        lat = row_upper_keys.get('LATITUDE')
        
        obj_id = row_upper_keys.get('ID')

        if lon is None or lat is None or obj_id is None:
            logger.debug(f"Skipping row due to missing ID/Lon/Lat. ID: {obj_id}, Lon: {lon}, Lat: {lat}")
            
            self.stats["invalid_rows_skipped"] += 1
            
            return None

        return {"type": "Feature", "id": str(obj_id), "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]}, "properties": properties}

    def _send_api_request_with_retry(self, method: str, url: str, headers: Dict, payload: Optional[Dict|List] = None) -> Tuple[bool, bool]:
        """Sends an API request with a robust retry mechanism. Returns (success, was_retried)."""
        was_retried = False
        
        for attempt in range(config.MAX_RETRIES):
            try:
                response = requests.request(method, url, headers=headers, json=payload, timeout=60)
                response.raise_for_status()
                
                return True, was_retried
            except requests.exceptions.RequestException as e:
                if e.response is not None and 400 <= e.response.status_code < 500:
                    logger.error(f"Client error {e.response.status_code} for {method} {url}, no retries. Response: {e.response.text}")
                    
                    return False, was_retried
                
                logger.warning(f"Attempt {attempt + 1}/{config.MAX_RETRIES} failed for {method} {url}. Error: {e}")
                
                was_retried = True
                self.stats["total_api_retries"] += 1
                
                time.sleep(config.RETRY_DELAY_BASE_SECONDS * (attempt + 1))
        
        logger.error(f"Request failed after {config.MAX_RETRIES} attempts: {method} {url}")
        
        return False, was_retried

    def _pre_flight_check(self) -> bool:
        """Checks if the asset is available and ready to receive data before starting the main sync."""
        logger.info("Performing pre-flight check to ensure asset is available...")
        
        api_url = f"{config.API_BASE_URL}/dynamic_asset/{config.DYNAMIC_ASSET_ID}"
        
        headers = {'Authorization': f'Bearer {config.MASTER_API_TOKEN}'}

        for i in range(PRE_FLIGHT_TIMEOUT_SECONDS // PRE_FLIGHT_RETRY_DELAY):
            try:
                response = requests.get(api_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    logger.info("Pre-flight check successful. Asset is available.")
                    
                    return True
                else:
                    logger.warning(f"Pre-flight check attempt {i+1} failed with status {response.status_code}. Retrying in {PRE_FLIGHT_RETRY_DELAY}s...")
            except requests.exceptions.RequestException as e:
                logger.warning(f"Pre-flight check attempt {i+1} failed with network error: {e}. Retrying in {PRE_FLIGHT_RETRY_DELAY}s...")
            
            time.sleep(PRE_FLIGHT_RETRY_DELAY)
            
        logger.error(f"Pre-flight check failed. Asset {config.DYNAMIC_ASSET_ID} was not available after {PRE_FLIGHT_TIMEOUT_SECONDS} seconds.")
        
        return False

    def _run_upserts(self, db: DatabaseConnector, last_sync_timestamp: str, last_known_ids_set: set):
        """Phase 1: Fetch, classify (add/update), and push new/updated records."""
        logger.info(f"Phase 1: Fetching records modified since {last_sync_timestamp}...")
        
        cursor = db.get_records_since(last_sync_timestamp)
        
        if not cursor: return
        
        columns = [d[0] for d in cursor.description]
        
        api_url = f"{config.API_BASE_URL}/dynamic_asset/{config.DYNAMIC_ASSET_ID}/data"
        
        headers = {'Authorization': f'Bearer {config.PUSH_DATA_ACCESS_TOKEN}', 'X-Brand': config.API_X_BRAND_HEADER}

        with tqdm(total=0, desc="DB Records Processed", unit="row", file=sys.stdout, position=0) as db_pbar:
            while True:
                db_chunk = cursor.fetchmany(config.DB_FETCH_CHUNK_SIZE)
                
                if not db_chunk: break

                self.stats["db_records_read"] += len(db_chunk)
                
                db_pbar.total = self.stats["db_records_read"]
                db_pbar.update(len(db_chunk))

                features_to_push = []
                
                for row in db_chunk:
                    feature = self._row_to_feature(dict(zip(columns, row)))
                    
                    if feature:
                        features_to_push.append(feature)
                        
                        if feature['id'] in last_known_ids_set:
                            self.stats['records_updated'] += 1
                        else:
                            self.stats['records_added'] += 1

                if not features_to_push: continue
                
                api_chunks = [features_to_push[i:i + config.API_PUSH_CHUNK_SIZE] for i in range(0, len(features_to_push), config.API_PUSH_CHUNK_SIZE)]
                
                with tqdm(total=len(features_to_push), desc="API Push (Upserts)", unit="feature", file=sys.stdout, position=1, leave=False) as api_pbar:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
                        future_to_chunk = {executor.submit(self._send_api_request_with_retry, "PUT", api_url, headers, {"type": "FeatureCollection", "features": chunk}): chunk for chunk in api_chunks}
                        
                        for future in concurrent.futures.as_completed(future_to_chunk):
                            chunk = future_to_chunk[future]
                            
                            try:
                                success, was_retried = future.result()
                                
                                if success:
                                    self.stats["push_success"] += len(chunk)
                                    
                                    if was_retried: self.stats["api_chunks_success_retries"] += 1
                                    else: self.stats["api_chunks_success_first_try"] += 1
                                else:
                                    self.stats["push_failed"] += len(chunk)
                                    self.stats["api_chunks_failed"] += 1
                            except Exception as exc:
                                self.stats["push_failed"] += len(chunk)
                                self.stats["api_chunks_failed"] += 1
                                
                                logger.error(f'API push chunk generated an exception: {exc}')

                            api_pbar.update(len(chunk))

    def _run_deletions(self, db: DatabaseConnector, last_known_ids: List[str]) -> List[str]:
        """Phase 2: Fetch all current IDs, compare, and delete stale records."""
        logger.info("Phase 2: Detecting deleted records...")
        
        current_ids_set = set(db.get_all_current_ids())
        ids_to_delete = list(set(last_known_ids) - current_ids_set)
        
        self.stats["records_deleted"] = len(ids_to_delete)
        self.stats["final_record_count"] = len(current_ids_set)
        
        if not ids_to_delete:
            logger.info("No records to delete.")
            
            return list(current_ids_set)
            
        logger.info(f"Found {len(ids_to_delete)} records to delete. Deleting in chunks...")
        
        api_url = f"{config.API_BASE_URL}/dynamic_asset/{config.DYNAMIC_ASSET_ID}/data"
        
        headers = {'Authorization': f'Bearer {config.PUSH_DATA_ACCESS_TOKEN}', 'X-Brand': config.API_X_BRAND_HEADER}
        
        chunks = [ids_to_delete[i:i + config.API_PUSH_CHUNK_SIZE] for i in range(0, len(ids_to_delete), config.API_PUSH_CHUNK_SIZE)]

        with tqdm(total=len(ids_to_delete), desc="Deleting Data", unit="ID", file=sys.stdout) as pbar:
            for chunk in chunks:
                success, _ = self._send_api_request_with_retry("DELETE", api_url, headers, payload=chunk)
                
                if success:
                    self.stats["delete_success"] += len(chunk)
                else:
                    self.stats["delete_failed"] += len(chunk)
                
                pbar.update(len(chunk))
                
        return list(current_ids_set)

    def _display_summary(self):
        """Prints a final, detailed summary of the sync operation."""
        summary = f"""
        \n================================================================
        SYNC OPERATION SUMMARY
        ================================================================
        DATABASE & DATA QUALITY:
        - Records Read from View:         {self.stats['db_records_read']}
        - Skipped Invalid Rows (no geo):  {self.stats['invalid_rows_skipped']}

        RECORD CHANGES:
        - Records Added:                  {self.stats['records_added']}
        - Records Updated:                {self.stats['records_updated']}
        - Records Deleted:                {self.stats['records_deleted']}
        
        API PUSH PERFORMANCE (UPSERTS):
        - Records Pushed Successfully:    {self.stats['push_success']}
        - Records Failed to Push:         {self.stats['push_failed']}
        - Chunks Succeeded (1st try):     {self.stats['api_chunks_success_first_try']}
        - Chunks Succeeded (w/ Retries):  {self.stats['api_chunks_success_retries']}
        - Chunks Failed Permanently:      {self.stats['api_chunks_failed']}

        API DELETE PERFORMANCE:
        - Records Deleted Successfully:   {self.stats['delete_success']}
        - Records Failed to Delete:       {self.stats['delete_failed']}

        FINAL STATE:
        - Total Records in Asset:         {self.stats['final_record_count']}
        ================================================================\n
        """
        sys.stdout.write(summary)
        
        logger.info(f"Final Stats: {self.stats}")

    def run(self):
        """Orchestrates the entire synchronization process."""
        start_time = datetime.now(timezone.utc)
        
        logger.info(f"Starting sync run at {start_time.isoformat()}")

        if not config.DYNAMIC_ASSET_ID or not config.PUSH_DATA_ACCESS_TOKEN:
            logger.error("DYNAMIC_ASSET_ID or PUSH_DATA_ACCESS_TOKEN is missing in .env. Cannot run sync.")
            
            return

        if not self._pre_flight_check():
            logger.critical("Aborting sync due to failed pre-flight check.")
            
            return

        last_sync_timestamp, last_known_ids = self._load_state()

        try:
            with DatabaseConnector() as db:
                self._run_upserts(db, last_sync_timestamp, set(last_known_ids))
                
                current_source_of_truth_ids = self._run_deletions(db, last_known_ids)
            
            if self.stats["push_failed"] > 0 or self.stats["delete_failed"] > 0:
                logger.error("Sync run completed with failures. State file will not be updated to prevent data loss on next run.")
            else:
                self._save_state(start_time, current_source_of_truth_ids)
                
                logger.info("Sync run completed successfully.")

        except Exception as e:
            logger.critical(f"A fatal error occurred during the sync process: {e}", exc_info=True)

        self._display_summary()
        end_time = datetime.now(timezone.utc)
        
        logger.info(f"Sync run finished at {end_time.isoformat()}. Duration: {end_time - start_time}")

def main():
    try:
        oracledb.init_oracle_client()
    except Exception as e:
        logger.error("Oracle Instant Client not found or failed to initialize.", exc_info=True)
        
        sys.exit(1)
        
    manager = SyncManager()
    manager.run()

if __name__ == "__main__":
    main()