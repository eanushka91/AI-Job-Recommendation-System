# tests/test_db/test_database_setup.py

import pytest
import psycopg2

# Import the functions/classes we are testing or need for setup
from app.db.database import get_db_connection, create_tables, init_db
# We might need settings for mocking, but not for the connection itself in mocked tests
# from app.config import settings


# --- Fixture for real DB connection (Optional, for integration tests) ---
@pytest.fixture(scope="module")
def db_conn_for_integration_tests():
    try:
        # Import settings here if needed for real connection details
        from app.config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

        conn_setup = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,  # Use TEST_* variables if configured
            user=DB_USER,
            password=DB_PASSWORD,
        )
        yield conn_setup
        conn_setup.close()
    except (ImportError, psycopg2.OperationalError) as e:
        pytest.skip(
            f"Skipping integration tests: Test DB connection/config failed: {e}"
        )


# --- Unit Tests for database functions (using mocking) ---


def test_get_db_connection_mocked(mocker):
    """Test get_db_connection when connection is successful (mocking psycopg2.connect)"""
    # Mock the actual database connection call
    mock_connect = mocker.patch("psycopg2.connect")
    mock_conn_obj = mocker.MagicMock(
        name="mock_db_conn_success"
    )  # Mock connection object
    mock_connect.return_value = mock_conn_obj

    # Mock the settings attributes checked within get_db_connection to prevent ConnectionError
    # Patch the 'app.db.database' namespace where get_db_connection imports settings
    mocker.patch("app.db.database.DB_HOST", "mock_host")
    mocker.patch("app.db.database.DB_PORT", "mock_port")
    mocker.patch("app.db.database.DB_NAME", "mock_db")
    mocker.patch("app.db.database.DB_USER", "mock_user")
    mocker.patch("app.db.database.DB_PASSWORD", "mock_pass")

    # Call the function under test
    returned_conn = get_db_connection()

    # Assert that psycopg2.connect was called with the (now mocked) settings values
    mock_connect.assert_called_once_with(
        host="mock_host",
        port="mock_port",
        dbname="mock_db",
        user="mock_user",
        password="mock_pass",
    )
    # Assert that the mocked connection object was returned
    assert returned_conn == mock_conn_obj


def test_get_db_connection_failure_mocked(mocker):
    """Test get_db_connection when psycopg2.connect raises an error"""
    # Mock the settings attributes to prevent config error first
    mocker.patch("app.db.database.DB_HOST", "mock_host")
    mocker.patch("app.db.database.DB_PORT", "mock_port")
    mocker.patch("app.db.database.DB_NAME", "mock_db")
    mocker.patch("app.db.database.DB_USER", "mock_user")
    mocker.patch("app.db.database.DB_PASSWORD", "mock_pass")

    # Mock psycopg2.connect to raise an error
    mock_connect = mocker.patch(
        "psycopg2.connect",
        side_effect=psycopg2.OperationalError("Mock connection failure"),
    )

    # Assert that calling get_db_connection raises the expected exception
    with pytest.raises(psycopg2.OperationalError, match="Mock connection failure"):
        get_db_connection()

    # Ensure connect was called
    mock_connect.assert_called_once()


def test_get_db_connection_config_error(mocker):
    """Test get_db_connection when configuration is incomplete"""
    # Mock only some settings to simulate incomplete configuration
    mocker.patch("app.db.database.DB_HOST", "mock_host")
    mocker.patch("app.db.database.DB_NAME", "mock_db")
    mocker.patch("app.db.database.DB_USER", "mock_user")
    # DB_PORT and DB_PASSWORD are intentionally not mocked or set to None
    mocker.patch("app.db.database.DB_PORT", None)
    mocker.patch("app.db.database.DB_PASSWORD", None)
    mock_connect = mocker.patch("psycopg2.connect")  # To ensure it's not called

    # Assert that the specific ConnectionError is raised
    with pytest.raises(ConnectionError, match="Database configuration is incomplete"):
        get_db_connection()

    # Ensure psycopg2.connect was NOT called because the config check failed first
    mock_connect.assert_not_called()


def test_create_tables_logic_mocked(mocker):
    """Test the logic within create_tables by mocking cursor interactions"""
    mock_conn_obj = mocker.MagicMock(closed=False, name="mock_conn_for_create")
    mock_cursor = mocker.MagicMock(name="mock_cursor_for_create")
    mock_conn_obj.cursor.return_value.__enter__.return_value = mock_cursor

    # Call the function with the mocked connection
    create_tables(mock_conn_obj)

    # Check that execute was called multiple times (at least for tables + indexes)
    assert mock_cursor.execute.call_count >= 5  # 3 tables + 2 indexes
    # Check that commit was called once
    mock_conn_obj.commit.assert_called_once()
    # Check rollback was not called
    mock_conn_obj.rollback.assert_not_called()


def test_create_tables_execute_error(mocker):
    """Test create_tables when cursor.execute raises an error"""
    mock_conn_obj = mocker.MagicMock(closed=False, name="mock_conn_create_error")
    mock_cursor = mocker.MagicMock(name="mock_cursor_create_error")
    mock_conn_obj.cursor.return_value.__enter__.return_value = mock_cursor
    # Simulate an error during the first execute call
    mock_cursor.execute.side_effect = psycopg2.Error("Mock table creation error")

    # Assert that the exception is raised and rollback is called
    with pytest.raises(psycopg2.Error, match="Mock table creation error"):
        create_tables(mock_conn_obj)

    mock_conn_obj.commit.assert_not_called()  # Commit should not happen on error
    mock_conn_obj.rollback.assert_called_once()  # Rollback should happen


def test_init_db_flow_mocked(mocker):
    """Test the overall flow of init_db using mocks"""
    mock_get_conn = mocker.patch("app.db.database.get_db_connection")
    mock_create_tables = mocker.patch("app.db.database.create_tables")
    mock_conn_obj = mocker.MagicMock(closed=False, name="mock_conn_for_init")
    mock_get_conn.return_value = mock_conn_obj

    init_db()  # Call the function under test

    mock_get_conn.assert_called_once()
    mock_create_tables.assert_called_once_with(mock_conn_obj)
    mock_conn_obj.close.assert_called_once()


def test_init_db_connection_error_mocked(mocker):
    """Test init_db when getting the connection fails"""
    # Simulate get_db_connection raising an error
    mock_get_conn = mocker.patch(
        "app.db.database.get_db_connection",
        side_effect=ConnectionError("Mock DB connection failed in init"),
    )
    mock_create_tables = mocker.patch("app.db.database.create_tables")
    # We don't need to mock 'close' here, as no connection object is created/returned

    init_db()  # Call the function, it should catch the exception

    mock_get_conn.assert_called_once()
    mock_create_tables.assert_not_called()  # create_tables should not be called
