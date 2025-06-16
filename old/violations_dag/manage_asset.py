# /manage_asset.py
import sys
import json
import logging
import requests
import oracledb
from dotenv import set_key
from typing import Dict, Any, List, Tuple

# Import shared modules
from common import config
from common.logging_setup import setup_logging
from common.attribute_mapper import ATTRIBUTE_MAPPER
from common.db_connector import DatabaseConnector


# Setup logger for this script
logger = setup_logging(config.LOG_FILE_MANAGE)


# ... The build_dynamic_schema function remains exactly the same ...
def build_dynamic_schema(db: DatabaseConnector) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Connects to the database and dynamically builds the attributes and filters
    lists based on the view's schema and data.
    """
    attributes = []
    filters = []

    try:
        db_columns = db.get_column_names()

        logger.info(f"Detected columns from view: {db_columns}")
    except Exception as e:
        logger.error(f"Could not fetch column metadata from view. Aborting. Error: {e}")

        raise

    for col_name in db_columns:
        if col_name.upper() == "ID":
            continue
        if col_name not in ATTRIBUTE_MAPPER:
            logger.warning(f"Column '{col_name}' not in ATTRIBUTE_MAPPER. Skipping.")

            continue

        map_info = ATTRIBUTE_MAPPER[col_name]
        
        attribute = {"id": col_name, "type": map_info["type"], "caption": map_info["en"], "localizations": {"caption": {"en": map_info["en"], "ar": map_info["ar"]}}}
        
        attributes.append(attribute)
        
        logger.debug(f"Generated attribute for '{col_name}': {attribute['id']}")

        if col_name == config.ASSET_PRIMARY_NAME_COLUMN:
            ns_attribute = {"id": f"{col_name}_ns", "type": "name", "caption": map_info["en"], "localizations": {"caption": {"en": map_info["en"], "ar": map_info["ar"]}}}
            attributes.append(ns_attribute)
            
            logger.info(f"Generated special 'name' attribute '{ns_attribute['id']}' for primary display.")

        filter_obj = {"attribute_id": col_name}
        
        try:
            if map_info["type"] == "string":
                filter_type, items = db.analyze_string_column(col_name)
                filter_obj["control_type"] = filter_type
                
                if items: filter_obj["items"] = items
            elif map_info["type"] in ["number", "date_time"]:
                filter_type = "date_time_range" if map_info["type"] == "date_time" else "range"
                min_val, max_val = db.analyze_numeric_date_column(col_name, map_info["type"])
                filter_obj["control_type"] = filter_type
                
                if min_val is not None: filter_obj["min"] = min_val
                if max_val is not None: filter_obj["max"] = max_val
            else:
                filter_obj["control_type"] = "text_box"
        except Exception as e:
            logger.warning(f"Analysis failed for column '{col_name}', defaulting filter to text_box. Error: {e}")
            
            filter_obj["control_type"] = "text_box"

        filter_obj["localizations"] = {"caption": {"en": f"{map_info['en']} Filter", "ar": f"فلتر {map_info['ar']}"}}
        filters.append(filter_obj)
        
        logger.debug(f"Generated filter for '{col_name}' pointing to attribute '{col_name}': {filter_obj['control_type']}")

    return attributes, filters


def execute_asset_operation():
    # ... This function remains exactly the same ...
    operation = config.ASSET_OPERATION
    
    logger.info(f"Starting asset '{operation}' process...")
    
    try:
        with DatabaseConnector() as db:
            attributes, filters = build_dynamic_schema(db)
    except Exception as e:
        logger.error(f"Failed to build dynamic schema from database. Process stopped. Error: {e}")
        
        return

    payload = { "name": config.ASSET_NAME, "description": config.ASSET_DESCRIPTION, "geometry_dimension": config.ASSET_GEOMETRY_DIMENSION, "localizations": { "name": {"en": config.ASSET_NAME, "ar": config.ASSET_NAME_AR}, "description": {"en": config.ASSET_DESCRIPTION, "ar": config.ASSET_DESCRIPTION_AR} }, "attribute_groups": [{ "name": config.ATTRIBUTE_GROUP_NAME, "localizations": {"name": {"en": config.ATTRIBUTE_GROUP_NAME, "ar": config.ATTRIBUTE_GROUP_NAME_AR}}, "attributes": attributes }], "filters": filters }
    headers = { 'Authorization': f'Bearer {config.MASTER_API_TOKEN}', 'X-Brand': config.API_X_BRAND_HEADER, 'Content-Type': 'application/json', 'accept': 'application/json' }
    
    api_url = f"{config.API_BASE_URL}/dynamic_asset"

    if operation == "CREATE":
        http_method = "POST"
    elif operation == "UPDATE":
        http_method = "PUT"
        
        if not config.DYNAMIC_ASSET_ID:
            logger.error("Cannot perform UPDATE. DYNAMIC_ASSET_ID is not set in .env file.")
            
            return
        payload["id"] = config.DYNAMIC_ASSET_ID
    else:
        logger.error(f"Invalid operation '{operation}' passed to execution function.")
        
        return

    logger.info(f"Sending {http_method} request to {api_url}...")
    
    try:
        response = requests.request(http_method, api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        response_data = response.json()
        
        logger.info(f"Asset successfully {operation.lower()}d.")
        logger.info(f"Response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
        
        if operation == "CREATE":
            new_asset_id = response_data.get("asset_id")
            new_token = response_data.get("access_token")
            
            if new_asset_id and new_token:
                logger.info("Updating .env file with new asset ID and push token...")
                
                set_key(".env", "DYNAMIC_ASSET_ID", new_asset_id)
                set_key(".env", "PUSH_DATA_ACCESS_TOKEN", new_token)
                
                logger.info(".env file updated successfully.")
            else:
                logger.error("Could not find 'asset_id' or 'access_token' in API response.")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error during asset operation: {e.response.status_code}")
        logger.error(f"Response Body: {e.response.text}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)


# *** NEW FUNCTION TO CLEAR ALL DATA ***
def clear_all_asset_data():
    """Sends a request to delete all data objects from the dynamic asset."""
    asset_id = config.DYNAMIC_ASSET_ID
    # IMPORTANT: Data operations use the PUSH_DATA_ACCESS_TOKEN
    access_token = config.PUSH_DATA_ACCESS_TOKEN

    if not asset_id or not access_token:
        logger.error("Cannot clear data. DYNAMIC_ASSET_ID or PUSH_DATA_ACCESS_TOKEN is not set in .env file.")
        
        return

    logger.warning(f"You are about to permanently delete ALL DATA from asset: {asset_id}")
    
    # Adding a strong confirmation step to prevent accidents
    confirm = input(f"This is irreversible. To confirm, please type the asset ID ('{asset_id}') and press Enter: ")

    if confirm.strip() != asset_id:
        logger.info("Confirmation failed. Clear data operation cancelled by user.")
        
        return

    api_url = f"{config.API_BASE_URL}/dynamic_asset/{asset_id}/data/all"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'X-Brand': config.API_X_BRAND_HEADER
    }

    logger.info(f"Sending DELETE request to {api_url} to clear all data...")
    
    try:
        response = requests.delete(api_url, headers=headers)
        response.raise_for_status()
        
        logger.info(f"All data successfully cleared from asset '{asset_id}'.")

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error during data clear operation: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during data clear: {e}", exc_info=True)


def main():
    """Main function to orchestrate the asset management task."""
    logger.info(f"Starting Asset Management Script. Operation set to: {config.ASSET_OPERATION}")

    try:
        config.validate_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        
        sys.exit(1)

    try:
        oracledb.init_oracle_client()
    except Exception as e:
        logger.error("Oracle Instant Client not found or failed to initialize.", exc_info=True)
        
        sys.exit(1)

    # *** UPDATED LOGIC TO ROUTE TO THE CORRECT FUNCTION ***
    if config.ASSET_OPERATION in ["CREATE", "UPDATE"]:
        execute_asset_operation()
    elif config.ASSET_OPERATION == "CLEAR_ALL_DATA":
        clear_all_asset_data()
    else: # This case is now handled by validate_config but kept as a safeguard
        logger.error(f"Invalid ASSET_OPERATION in .env file: '{config.ASSET_OPERATION}'.")
        
        sys.exit(1)

    logger.info("Script finished.")


if __name__ == "__main__":
    main()