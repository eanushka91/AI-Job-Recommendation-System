import pytest
import psycopg2

from app.db.database import get_db_connection, create_tables, init_db


@pytest.fixture(scope="module")
def db_conn_for_integration_tests():
    try:
        from app.config.settings import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

        conn_setup = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        yield conn_setup
        conn_setup.close()
    except (ImportError, psycopg2.OperationalError) as e:
        pytest.skip(
            f"Skipping integration tests: Test DB connection/config failed: {e}"
        )


def test_get_db_connection_mocked(mocker):
    """Test get_db_connection when connection is successful (mocking psycopg2.connect)"""
    mock_connect = mocker.patch("psycopg2.connect")
    mock_conn_obj = mocker.MagicMock(name="mock_db_conn_success")
    mock_connect.return_value = mock_conn_obj

    mocker.patch("app.db.database.DB_HOST", "mock_host")
    mocker.patch("app.db.database.DB_PORT", "mock_port")
    mocker.patch("app.db.database.DB_NAME", "mock_db")
    mocker.patch("app.db.database.DB_USER", "mock_user")
    mocker.patch("app.db.database.DB_PASSWORD", "mock_pass")

    returned_conn = get_db_connection()

    mock_connect.assert_called_once_with(
        host="mock_host",
        port="mock_port",
        dbname="mock_db",
        user="mock_user",
        password="mock_pass",
    )
    assert returned_conn == mock_conn_obj


def test_get_db_connection_failure_mocked(mocker):
    """Test get_db_connection when psycopg2.connect raises an error"""
    mocker.patch("app.db.database.DB_HOST", "mock_host")
    mocker.patch("app.db.database.DB_PORT", "mock_port")
    mocker.patch("app.db.database.DB_NAME", "mock_db")
    mocker.patch("app.db.database.DB_USER", "mock_user")
    mocker.patch("app.db.database.DB_PASSWORD", "mock_pass")

    mock_connect = mocker.patch(
        "psycopg2.connect",
        side_effect=psycopg2.OperationalError("Mock connection failure"),
    )

    with pytest.raises(psycopg2.OperationalError, match="Mock connection failure"):
        get_db_connection()

    mock_connect.assert_called_once()


def test_get_db_connection_config_error(mocker):
    """Test get_db_connection when configuration is incomplete"""
    mocker.patch("app.db.database.DB_HOST", "mock_host")
    mocker.patch("app.db.database.DB_NAME", "mock_db")
    mocker.patch("app.db.database.DB_USER", "mock_user")
    mocker.patch("app.db.database.DB_PORT", None)
    mocker.patch("app.db.database.DB_PASSWORD", None)
    mock_connect = mocker.patch("psycopg2.connect")

    with pytest.raises(ConnectionError, match="Database configuration is incomplete"):
        get_db_connection()

    mock_connect.assert_not_called()


def test_create_tables_logic_mocked(mocker):
    """Test the logic within create_tables by mocking cursor interactions"""
    mock_conn_obj = mocker.MagicMock(closed=False, name="mock_conn_for_create")
    mock_cursor = mocker.MagicMock(name="mock_cursor_for_create")
    mock_conn_obj.cursor.return_value.__enter__.return_value = mock_cursor

    create_tables(mock_conn_obj)

    assert mock_cursor.execute.call_count >= 5
    mock_conn_obj.commit.assert_called_once()
    mock_conn_obj.rollback.assert_not_called()


def test_create_tables_execute_error(mocker):
    """Test create_tables when cursor.execute raises an error"""
    mock_conn_obj = mocker.MagicMock(closed=False, name="mock_conn_create_error")
    mock_cursor = mocker.MagicMock(name="mock_cursor_create_error")
    mock_conn_obj.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.execute.side_effect = psycopg2.Error("Mock table creation error")

    with pytest.raises(psycopg2.Error, match="Mock table creation error"):
        create_tables(mock_conn_obj)

    mock_conn_obj.commit.assert_not_called()
    mock_conn_obj.rollback.assert_called_once()


def test_init_db_flow_mocked(mocker):
    """Test the overall flow of init_db using mocks"""
    mock_get_conn = mocker.patch("app.db.database.get_db_connection")
    mock_create_tables = mocker.patch("app.db.database.create_tables")
    mock_conn_obj = mocker.MagicMock(closed=False, name="mock_conn_for_init")
    mock_get_conn.return_value = mock_conn_obj

    init_db()

    mock_get_conn.assert_called_once()
    mock_create_tables.assert_called_once_with(mock_conn_obj)
    mock_conn_obj.close.assert_called_once()


def test_init_db_connection_error_mocked(mocker):
    """Test init_db when getting the connection fails"""
    mock_get_conn = mocker.patch(
        "app.db.database.get_db_connection",
        side_effect=ConnectionError("Mock DB connection failed in init"),
    )
    mock_create_tables = mocker.patch("app.db.database.create_tables")

    init_db()

    mock_get_conn.assert_called_once()
    mock_create_tables.assert_not_called()
