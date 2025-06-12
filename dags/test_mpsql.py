from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.exceptions import AirflowException

# Define the Python callable function to test the PostgreSQL connection
def test_postgres_connection_callable(db_conn_id: str):
    """
    Tests the connection to a PostgreSQL database using the provided Airflow connection ID.

    Args:
        db_conn_id: The Airflow Connection ID for the PostgreSQL database.
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

        # 3. Create a cursor and execute a simple query to verify connectivity
        # A simple SELECT 1 is often used to check if the database is alive and reachable
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()

        if result and result[0] == 1:
            print(f"PostgreSQL database connection test successful! Query result: {result}")
        else:
            raise AirflowException(f"PostgreSQL connection test failed: Unexpected query result {result}")

    except Exception as e:
        # Catch any exceptions that occur during the connection or query
        print(f"Error testing PostgreSQL connection for ID '{db_conn_id}': {e}")
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
    dag_id="postgres_connection_test_dag",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    catchup=False,
    schedule=None,
    tags=["database", "connection", "test", "postgresql"],
    doc_md="""
    ### PostgreSQL Connection Test DAG

    This DAG contains a single task that uses `PostgresHook` to test
    connectivity to a PostgreSQL database specified by an Airflow Connection ID.

    **Instructions:**
    1.  Ensure you have a PostgreSQL connection configured in your Airflow UI
        under Admin -> Connections.
    2.  Set the `db_connection_id` variable below to match your configured
        connection ID (e.g., `postgres_default` or `my_custom_pg_conn`).
    3.  Make sure the `apache-airflow-providers-postgres` package is installed
        in your Airflow environment (`pip install apache-airflow-providers-postgres`).
    """
) as dag:
    # IMPORTANT: Replace 'postgres_default' with your actual Airflow PostgreSQL Connection ID
    # This ID must be configured in your Airflow UI (Admin -> Connections)
    db_connection_id = "test_conn" 

    test_connection_task = PythonOperator(
        task_id="test_postgres_connection",
        python_callable=test_postgres_connection_callable,
        op_kwargs={
            "db_conn_id": db_connection_id,
        },
    )