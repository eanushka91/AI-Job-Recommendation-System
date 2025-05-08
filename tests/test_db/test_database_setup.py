# tests/test_db/test_database_setup.py

import pytest
import psycopg2
# from psycopg2.extras import RealDictCursor # Removed F401
# Assuming these are needed for the tests
from app.db.database import get_db_connection, create_tables, init_db
from app.config import settings # Assuming settings are needed for connection details

# Fixture for a real test DB connection (use with caution)
@pytest.fixture(scope="module")
def db_conn_for_setup_tests():
    try:
        # Use test DB credentials from settings or environment variables
        conn_setup = psycopg2.connect(
            host=settings.DB_HOST, # Ideally TEST_DB_HOST
            port=settings.DB_PORT,
            dbname=settings.DB_NAME, # Ideally TEST_DB_NAME
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        yield conn_setup
        conn_setup.close()
    except psycopg2.OperationalError as e:
        pytest.skip(f"Test DB connection failed: {e}")

# Test the connection function itself (mocking the actual connection)
def test_get_db_connection_mocked(mocker):
    mock_connect = mocker.patch("psycopg2.connect")
    mock_conn_obj = mocker.MagicMock()
    mock_connect.return_value = mock_conn_obj

    returned_conn = get_db_connection() # Call the function under test

    mock_connect.assert_called_once_with(
        host=settings.DB_HOST, port=settings.DB_PORT, dbname=settings.DB_NAME,
        user=settings.DB_USER, password=settings.DB_PASSWORD
    )
    assert returned_conn == mock_conn_obj

def test_get_db_connection_failure_mocked(mocker):
    mocker.patch("psycopg2.connect", side_effect=psycopg2.OperationalError("Connection failed test"))
    with pytest.raises(psycopg2.OperationalError):
        get_db_connection()

# Test the logic of create_tables by mocking cursor interactions
def test_create_tables_logic_mocked(mocker):
    # We don't need a real connection for this unit test of the logic
    mock_conn_obj = mocker.MagicMock(closed=False) # Mock connection object
    mock_cursor = mocker.MagicMock() # Mock cursor object
    # Setup the context manager for 'with conn.cursor() as cur:'
    mock_conn_obj.cursor.return_value.__enter__.return_value = mock_cursor

    # Call the function with the mocked connection
    create_tables(mock_conn_obj)

    # Assertions: Check if execute was called for each table and commit was called
    assert mock_cursor.execute.call_count >= 3 # users, resumes, job_recommendations
    execute_calls_args = [call.args[0] for call in mock_cursor.execute.call_args_list] # Get the SQL strings
    assert any("CREATE TABLE IF NOT EXISTS users" in sql for sql in execute_calls_args)
    assert any("CREATE TABLE IF NOT EXISTS resumes" in sql for sql in execute_calls_args)
    assert any("CREATE TABLE IF NOT EXISTS job_recommendations" in sql for sql in execute_calls_args)
    assert any("CREATE INDEX IF NOT EXISTS" in sql for sql in execute_calls_args) # Check index creation too
    mock_conn_obj.commit.assert_called_once() # Ensure commit is called

# Test the init_db function's flow (mocking helpers)
def test_init_db_flow_mocked(mocker):
    mock_get_conn = mocker.patch("app.db.database.get_db_connection")
    mock_create_tables = mocker.patch("app.db.database.create_tables")
    mock_conn_obj = mocker.MagicMock(closed=False)
    mock_get_conn.return_value = mock_conn_obj

    init_db() # Call the function under test

    mock_get_conn.assert_called_once()
    mock_create_tables.assert_called_once_with(mock_conn_obj)
    mock_conn_obj.close.assert_called_once()

def test_init_db_connection_error_mocked(mocker):
    # Simulate get_db_connection failing
    mock_get_conn = mocker.patch("app.db.database.get_db_connection", side_effect=Exception("DB connection failed"))
    mock_create_tables = mocker.patch("app.db.database.create_tables")
    mock_conn_close = mocker.patch.object(psycopg2.extensions.connection, 'close', autospec=True) # Mock close on the class

    init_db() # Call the function, it should handle the exception

    mock_get_conn.assert_called_once()
    mock_create_tables.assert_not_called() # Should not be called if connection fails
    mock_conn_close.assert_not_called() # Close should not be called if connection wasn't established

