# /common/db_connector.py
import oracledb
import logging
from typing import Optional, List, Dict, Any, Tuple
from dateutil.parser import parse as date_parse  # Import the date parser
from . import config

logger = logging.getLogger(__name__)

class DatabaseConnector:
    """A class to handle all interactions with the Oracle database."""
    def __init__(self):
        self.dsn = oracledb.makedsn(config.DB_HOST, config.DB_PORT, service_name=config.DB_SERVICE_NAME)
        self.conn: Optional[oracledb.Connection] = None
        
        self.qualified_view_name = f'"{config.DB_SCHEMA}"."{config.DB_VIEW_NAME}"'
        
        logger.info(f"DatabaseConnector initialized to use view: {self.qualified_view_name}")

    def __enter__(self):
        try:
            logger.info(f"Connecting to Oracle DB as user '{config.DB_USER}' at {config.DB_HOST}...")
            
            self.conn = oracledb.connect(user=config.DB_USER, password=config.DB_PASSWORD, dsn=self.dsn)
            
            logger.info(f"Oracle DB connection successful. Version: {self.conn.version}")
            
            return self
        except Exception as e:
            logger.error(f"FATAL: Could not connect to Oracle Database. Error: {e}", exc_info=True)
            
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
            
            logger.info("Oracle DB connection closed.")

    def get_column_names(self) -> List[str]:
        query = f'SELECT * FROM {self.qualified_view_name} WHERE ROWNUM = 1'
        
        with self.conn.cursor() as cursor:
            cursor.execute(query)
            
            return [desc[0] for desc in cursor.description]

    def analyze_string_column(self, col_name: str) -> Tuple[str, Optional[List[Dict[str,str]]]]:
        with self.conn.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(DISTINCT "{col_name}") FROM {self.qualified_view_name}')
            
            distinct_count = cursor.fetchone()[0]
            
            logger.debug(f"Column '{col_name}' has {distinct_count} distinct values.")
            
            if 0 < distinct_count <= 50:
                cursor.execute(f'SELECT DISTINCT "{col_name}" FROM {self.qualified_view_name} WHERE "{col_name}" IS NOT NULL')
                
                items = [{"value": str(row[0]), "caption": str(row[0])} for row in cursor.fetchall()]
                
                return "check_box_list", items
            return "text_box", None

    def analyze_numeric_date_column(self, col_name: str, col_type: str) -> Tuple[Optional[Any], Optional[Any]]:
        """Analyzes a numeric or date column to get min/max values."""
        with self.conn.cursor() as cursor:
            query = f'SELECT MIN("{col_name}"), MAX("{col_name}") FROM {self.qualified_view_name}'
            
            cursor.execute(query)
            
            min_val, max_val = cursor.fetchone()

            if col_type == "date_time" and min_val and max_val:
                # *** FIX: Parse the string values into datetime objects first ***
                try:
                    # Parse with dayfirst=True to handle 'DD/MM/YYYY'
                    min_dt = date_parse(min_val, dayfirst=True) if isinstance(min_val, str) else min_val
                    max_dt = date_parse(max_val, dayfirst=True) if isinstance(max_val, str) else max_val
                    
                    # Convert to unix timestamp in milliseconds
                    return int(min_dt.timestamp() * 1000), int(max_dt.timestamp() * 1000)
                except Exception as e:
                    logger.error(f"Could not parse date strings for column '{col_name}'. Min: '{min_val}', Max: '{max_val}'. Error: {e}")
                    
                    return None, None # Return None if parsing fails

            if col_type == "number" and min_val is not None and max_val is not None:
                return float(min_val), float(max_val)
            
            return None, None
            
    def get_records_since(self, timestamp: str) -> Optional[oracledb.Cursor]:
        try:
            cursor = self.conn.cursor()

            query = f"""
                SELECT * FROM {self.qualified_view_name}
                WHERE "created_date" > TO_TIMESTAMP_TZ(:ts, 'YYYY-MM-DD"T"HH24:MI:SS.FF TZH:TZM')
            """
            cursor.execute(query, ts=timestamp)

            return cursor
        except Exception as e:
            logger.error(f"Failed to fetch records since {timestamp}. Error: {e}")

            return None
            
    def get_all_current_ids(self) -> List[str]:
        ids = []

        try:
            with self.conn.cursor() as cursor:
                query = f'SELECT "id" FROM {self.qualified_view_name}'

                cursor.execute(query)

                for row in cursor:
                    ids.append(str(row[0]))
            return ids
        except Exception as e:
            logger.error(f"Failed to fetch all current IDs. Error: {e}")

            return []