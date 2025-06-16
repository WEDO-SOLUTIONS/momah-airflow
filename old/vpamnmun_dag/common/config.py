# /common/config.py
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# --- DATABASE CONFIG ---
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_SCHEMA = os.getenv("DB_SCHEMA")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", 1521))
DB_SERVICE_NAME = os.getenv("DB_SERVICE_NAME")
DB_VIEW_NAME = os.getenv("DB_VIEW_NAME")

# --- API CONFIG ---
MASTER_API_TOKEN = os.getenv("MASTER_API_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL")
API_X_BRAND_HEADER = os.getenv("API_X_BRAND_HEADER", "2gis")
DYNAMIC_ASSET_ID = os.getenv("DYNAMIC_ASSET_ID")
PUSH_DATA_ACCESS_TOKEN = os.getenv("PUSH_DATA_ACCESS_TOKEN")

# --- MANAGE_ASSET.PY CONFIG ---
ASSET_OPERATION = os.getenv("ASSET_OPERATION", "CREATE").upper()
ASSET_NAME = os.getenv("ASSET_NAME")
ASSET_DESCRIPTION = os.getenv("ASSET_DESCRIPTION")
ASSET_NAME_AR = os.getenv("ASSET_NAME_AR")
ASSET_DESCRIPTION_AR = os.getenv("ASSET_DESCRIPTION_AR")
ASSET_GEOMETRY_DIMENSION = os.getenv("ASSET_GEOMETRY_DIMENSION", "point")
ASSET_PRIMARY_NAME_COLUMN = os.getenv("ASSET_PRIMARY_NAME_COLUMN")
ASSET_PRIMARY_NAME_COLUMN_AR = os.getenv("ASSET_PRIMARY_NAME_COLUMN_AR")
ATTRIBUTE_GROUP_NAME = os.getenv("ATTRIBUTE_GROUP_NAME")
ATTRIBUTE_GROUP_NAME_AR = os.getenv("ATTRIBUTE_GROUP_NAME_AR")

# --- SYNC_DATA.PY CONFIG ---
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 10))
DB_FETCH_CHUNK_SIZE = int(os.getenv("DB_FETCH_CHUNK_SIZE", 50000))
API_PUSH_CHUNK_SIZE = int(os.getenv("API_PUSH_CHUNK_SIZE", 100))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 5))
RETRY_DELAY_BASE_SECONDS = int(os.getenv("RETRY_DELAY_BASE_SECONDS", 5))

# --- LOGGING CONFIG ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE_MANAGE = os.getenv("LOG_FILE_MANAGE", "manage_asset.log")
LOG_FILE_SYNC = os.getenv("LOG_FILE_SYNC", "sync_data.log")

def validate_config():
    """Validates that critical configuration variables are set."""
    valid_operations = ["CREATE", "UPDATE", "CLEAR_ALL_DATA"]
    
    if ASSET_OPERATION not in valid_operations:
        raise ValueError(f"Invalid ASSET_OPERATION: {ASSET_OPERATION}. Must be one of {valid_operations}.")

    critical_vars_for_manage = [
        DB_USER, DB_PASSWORD, DB_SCHEMA, DB_HOST, DB_SERVICE_NAME, DB_VIEW_NAME,
        MASTER_API_TOKEN, API_BASE_URL, ASSET_NAME
    ]
    
    if ASSET_OPERATION in ["CREATE", "UPDATE"] and not all(critical_vars_for_manage):
        raise ValueError("For CREATE/UPDATE, critical DB/API/Asset Name variables are missing in .env.")
