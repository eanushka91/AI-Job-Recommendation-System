import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from app.db.database import get_db_connection, create_tables, init_db
from app.config import settings # DB Credentials

# --- WARNING: These tests might try to connect to your actual DB ---
# --- It's STRONGLY recommended to use a dedicated TEST DATABASE ---
# --- and configure it in settings (e.g., TEST_DB_HOST, etc.) ---
# --- or mock the psycopg2.connect call entirely for unit tests ---

@pytest.fixture(scope="module")
def db_conn_for_setup_tests():
    # Ensure you're using test DB credentials for this
    # This is just a basic example; a proper test DB setup is better
    try:
        conn = psycopg2.connect(
            host=settings.DB_HOST, # Ideally settings.TEST_DB_HOST
            port=settings.DB_PORT,
            dbname=settings.DB_NAME, # Ideally settings.TEST_DB_NAME
            user=settings.DB_USER,
            password=settings.DB_PASSWORD
        )
        yield conn
        conn.close()
    except psycopg2.OperationalError as e:
        pytest.skip(f"Test DB not available or connection failed: {e}")


def test_get_db_connection(mocker):
    # Mock psycopg2.connect to avoid actual DB connection for this unit test
    mock_connect = mocker.patch("psycopg2.connect")
    mock_conn_obj = mocker.MagicMock()
    mock_connect.return_value = mock_conn_obj

    conn = get_db_connection()
    mock_connect.assert_called_once_with(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=settings.DB_NAME,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD
    )
    assert conn == mock_conn_obj

def test_get_db_connection_failure(mocker):
    mocker.patch("psycopg2.connect", side_effect=psycopg2.OperationalError("Connection failed"))
    with pytest.raises(psycopg2.OperationalError): # Or the wrapped exception if get_db_connection wraps it
        get_db_connection()

# This test WILL try to create tables. Use with caution or mock heavily.
def test_create_tables(db_conn_for_setup_tests, mocker):
    # We'll check if the execute commands are called correctly
    # For a true integration test, you'd check if tables exist afterwards
    conn = db_conn_for_setup_tests
    mock_cursor = mocker.MagicMock()
    mock_conn_obj = mocker.MagicMock()
    mock_conn_obj.cursor.return_value.__enter__.return_value = mock_cursor # For 'with conn.cursor() as cur:'

    # Replace the actual connection with a mock for this test of create_tables' logic
    mocker.patch("app.db.database.get_db_connection", return_value=mock_conn_obj)

    # Call create_tables with the mock_conn_obj that has a mock_cursor
    create_tables(mock_conn_obj)

    # Check that execute was called for each table
    assert mock_cursor.execute.call_count >= 3 # users, resumes, job_recommendations
    execute_calls = [call[0][0] for call in mock_cursor.execute.call_args_list]

    assert any("CREATE TABLE IF NOT EXISTS users" in call for call in execute_calls)
    assert any("CREATE TABLE IF NOT EXISTS resumes" in call for call in execute_calls)
    assert any("CREATE TABLE IF NOT EXISTS job_recommendations" in call for call in execute_calls)
    mock_conn_obj.commit.assert_called_once()

def test_init_db(mocker):
    mock_get_conn = mocker.patch("app.db.database.get_db_connection")
    mock_create_tables = mocker.patch("app.db.database.create_tables")
    mock_conn_obj = mocker.MagicMock()
    mock_get_conn.return_value = mock_conn_obj

    init_db()

    mock_get_conn.assert_called_once()
    mock_create_tables.assert_called_once_with(mock_conn_obj)
    mock_conn_obj.close.assert_called_once()

def test_init_db_connection_error(mocker):
    mocker.patch("app.db.database.get_db_connection", side_effect=Exception("DB conn error"))
    mock_create_tables = mocker.patch("app.db.database.create_tables")
    # init_db should catch the exception and print, not re-raise
    init_db()
    mock_create_tables.assert_not_called() # Should not be called if connection fails