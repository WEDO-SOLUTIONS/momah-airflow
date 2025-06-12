from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.exceptions import AirflowException

# Define the Python callable function to test the PostgreSQL connection
def test_postgres_connection_callable(db_conn_id: str, sql_query: str, query_params: tuple = None):
    """
    Tests the connection to a PostgreSQL database using the provided Airflow connection ID
    and executes a specified SQL query with optional parameters.

    Args:
        db_conn_id: The Airflow Connection ID for the PostgreSQL database.
        sql_query: The SQL statement to execute.
        query_params: An optional tuple of parameters to pass to the SQL query.
    """
    hook = None  # Initialize hook to None for proper cleanup
    conn = None  # Initialize conn to None for proper cleanup
    try:
        # 1. Instantiate the PostgresHook with the given connection ID
        # The PostgresHook abstracts away the connection details stored in Airflow UI
        print(f"Attempting to get connection for ID: {db_conn_id}")
        hook = PostgresHook(postgres_conn_id=db_conn_id)

        # 2. Get a database connection object from the hook
        # This will attempt to connect to the database using the configured details
        conn = hook.get_conn()
        print("Successfully obtained PostgreSQL connection.")

        # 3. Create a cursor and execute the specified query
        cursor = conn.cursor()
        print(f"Executing SQL query: {sql_query}")
        if query_params:
            print(f"With parameters: {query_params}")
            cursor.execute(sql_query, query_params)
        else:
            cursor.execute(sql_query)

        # 4. Attempt to fetch results, if any
        # For a SELECT query, we can fetch rows. For a test, we might just check if it ran without error.
        results = cursor.fetchall() # Use fetchall() as the query might return multiple rows/columns
        
        # This part assumes the query is expected to return *something* or at least not fail.
        # For a connection test, simply successful execution is often enough.
        if results:
            print(f"SQL query executed successfully. First row of results: {results[0]}")
        else:
            print("SQL query executed successfully, no rows returned (as expected or due to no matching data).")

        # Commit the transaction if necessary (for DDL/DML, not typically for SELECT)
        # conn.commit() # Uncomment if your query involves DDL/DML and needs committing

    except Exception as e:
        # Catch any exceptions that occur during the connection or query
        print(f"Error testing PostgreSQL connection for ID '{db_conn_id}' with query:\n{sql_query}\nError: {e}")
        # Re-raise the exception to mark the task as failed in Airflow
        raise AirflowException(f"PostgreSQL connection test failed: {e}")
    finally:
        # Ensure the connection is closed even if an error occurs
        if conn:
            print("Closing PostgreSQL connection.")
            conn.close()
        if hook:
            print("PostgresHook cleanup complete.")

# Define the DAG
with DAG(
    dag_id="postgres_connection_test_dag_with_custom_query",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    catchup=False,
    schedule=None,
    tags=["database", "connection", "test", "postgresql", "sql_query"],
    doc_md="""
    ### PostgreSQL Connection Test DAG

    This DAG contains a single task that uses `PostgresHook` to test
    connectivity to a PostgreSQL database specified by an Airflow Connection ID.
    It now includes a custom SQL query with parameters.

    **Instructions:**
    1.  Ensure you have a PostgreSQL connection configured in your Airflow UI
        under Admin -> Connections.
    2.  Set the `db_connection_id` variable below to match your configured
        connection ID (e.g., `postgres_default` or `my_custom_pg_conn`).
    3.  Make sure the `apache-airflow-providers-postgres` package is installed
        in your Airflow environment (`pip install apache-airflow-providers-postgres`).
    4.  **Adjust `sql_query_statement` and `sql_query_parameters`**
        to match your actual requirements for the `get_pois_full_dual_lang_bbox` function.
    """
) as dag:
    # IMPORTANT: Replace 'postgres_default' with your actual Airflow PostgreSQL Connection ID
    # This ID must be configured in your Airflow UI (Admin -> Connections)
    db_connection_id = "test_conn"

    # Define the new SQL statement you want to test
    # Note: PostgreSQL uses $1, $2, etc., for positional parameters
    sql_query_statement = """
        SELECT
            id,
            category_id AS "categoryId",
            category_name_en AS "categoryName",
            description_en AS "description",
            title_en AS "title",
            latitude,
            longitude,
            address_en AS "address",
            contact_info_en AS "contactInfo"
        FROM get_pois_full_dual_lang_bbox($1, $2, $3, $4, $5);
    """

    # Define parameters for the SQL query.
    # IMPORTANT: These are placeholder values. You MUST replace them with
    # appropriate values for your get_pois_full_dual_lang_bbox function.
    # The order of values in this tuple must match the order of $1, $2, etc., in your SQL.
    # Example placeholder values for bounding box (min_lat, min_lon, max_lat, max_lon, language_id)
    sql_query_parameters = (
        24.0,  # $1: min_latitude (e.g., southern boundary)
        46.0,  # $2: min_longitude (e.g., western boundary)
        25.0,  # $3: max_latitude (e.g., northern boundary)
        47.0,  # $4: max_longitude (e.g., eastern boundary)
        1      # $5: language_id (e.g., 1 for English if that's your schema's ID)
    )

    test_connection_task = PythonOperator(
        task_id="test_postgres_connection_with_custom_query",
        python_callable=test_postgres_connection_callable,
        op_kwargs={
            "db_conn_id": db_connection_id,
            "sql_query": sql_query_statement,
            "query_params": sql_query_parameters,
        },
    )
