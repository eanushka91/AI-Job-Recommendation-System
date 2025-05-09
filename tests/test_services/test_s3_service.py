import pytest
from unittest.mock import MagicMock
import io
import re

from app.services.s3_service import S3Service
from app.config import settings

from botocore.exceptions import NoCredentialsError, ClientError


@pytest.fixture
def mock_boto3_s3_client(mocker):
    """Mocks boto3.client('s3') to return a mock S3 client instance."""
    mock_s3_instance = MagicMock(name="MockBoto3S3ClientInstance")
    mocker.patch('boto3.client', return_value=mock_s3_instance)
    return mock_s3_instance


@pytest.fixture
def mock_upload_file_obj():
    """
    Creates a mock UploadFile-like object.
    The 'file' attribute is a real BytesIO stream with a mocked 'seek' method.
    """
    file_content = b"dummy binary content for testing s3 upload"
    bytes_io_stream = io.BytesIO(file_content)

    upload_file_wrapper_mock = MagicMock(name="MockFastAPIUploadFile")
    upload_file_wrapper_mock.file = bytes_io_stream
    upload_file_wrapper_mock.filename = "test_cv_file.pdf"

    bytes_io_stream.seek = MagicMock(return_value=0, name="MockBytesIOSeekMethod")
    return upload_file_wrapper_mock


class TestS3ServiceUpload:
    def test_upload_file_success_with_filename_from_file_obj(
            self, mock_boto3_s3_client, mock_upload_file_obj, capsys
    ):
        expected_base_filename = mock_upload_file_obj.filename
        expected_s3_object_key = f"uploads/{expected_base_filename}"
        expected_s3_url = f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/{expected_s3_object_key}"

        actual_s3_url = S3Service.upload_file(file_obj=mock_upload_file_obj)

        assert actual_s3_url == expected_s3_url
        mock_upload_file_obj.file.seek.assert_called_once_with(0)
        mock_boto3_s3_client.upload_fileobj.assert_called_once_with(
            mock_upload_file_obj.file,
            settings.S3_BUCKET_NAME,
            expected_s3_object_key
        )
        captured = capsys.readouterr()
        assert "S3 Upload Error" not in captured.out

    def test_upload_file_success_with_explicit_object_name(
            self, mock_boto3_s3_client, mock_upload_file_obj, capsys
    ):
        provided_object_name = "custom/path/my_document.docx"
        expected_s3_object_key = f"uploads/{provided_object_name}"
        expected_s3_url = f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/{expected_s3_object_key}"

        actual_s3_url = S3Service.upload_file(
            file_obj=mock_upload_file_obj, object_name=provided_object_name
        )

        assert actual_s3_url == expected_s3_url
        mock_upload_file_obj.file.seek.assert_called_once_with(0)
        mock_boto3_s3_client.upload_fileobj.assert_called_once_with(
            mock_upload_file_obj.file,
            settings.S3_BUCKET_NAME,
            expected_s3_object_key
        )
        captured = capsys.readouterr()
        assert "S3 Upload Error" not in captured.out

    def test_upload_file_no_bucket_name_configured(self, mock_boto3_s3_client, mock_upload_file_obj, mocker, capsys):
        mocker.patch("app.services.s3_service.S3_BUCKET_NAME", "")

        with pytest.raises(Exception, match="S3_BUCKET_NAME is not configured."):
            S3Service.upload_file(file_obj=mock_upload_file_obj)

        captured = capsys.readouterr()
        assert "S3 Upload Error: S3_BUCKET_NAME is not configured." in captured.out
        mock_boto3_s3_client.upload_fileobj.assert_not_called()

    def test_upload_file_no_credentials_error(
            self, mock_boto3_s3_client, mock_upload_file_obj, capsys
    ):
        mock_boto3_s3_client.upload_fileobj.side_effect = NoCredentialsError()

        with pytest.raises(Exception, match="AWS credentials not available"):
            S3Service.upload_file(file_obj=mock_upload_file_obj)

        mock_upload_file_obj.file.seek.assert_called_once_with(0)
        captured = capsys.readouterr()
        assert "S3 Upload Error: AWS credentials not available" in captured.out

    def test_upload_file_boto_client_error(
            self, mock_boto3_s3_client, mock_upload_file_obj, capsys
    ):
        error_message_detail = "Mocked Boto3 ClientError (e.g., AccessDenied)"
        operation_name = "UploadFileobj"
        error_code = "AccessDenied"

        full_error_str = f"An error occurred ({error_code}) when calling the {operation_name} operation: {error_message_detail}"

        error_response = {'Error': {'Code': error_code, 'Message': error_message_detail}}
        mock_boto3_s3_client.upload_fileobj.side_effect = ClientError(
            error_response=error_response, operation_name=operation_name
        )

        expected_match_pattern = re.escape(f"S3 upload error (ClientError): {full_error_str}")

        with pytest.raises(Exception, match=expected_match_pattern):
            S3Service.upload_file(file_obj=mock_upload_file_obj)

        mock_upload_file_obj.file.seek.assert_called_once_with(0)
        captured = capsys.readouterr()
        assert f"S3 Upload Error (ClientError): {full_error_str}" in captured.out

    def test_upload_file_generic_exception_during_upload(
            self, mock_boto3_s3_client, mock_upload_file_obj, capsys
    ):
        generic_error_msg = "A very unexpected network problem!"
        mock_boto3_s3_client.upload_fileobj.side_effect = Exception(generic_error_msg)

        expected_match_pattern = re.escape(f"S3 upload error (Generic): {generic_error_msg}")

        with pytest.raises(Exception, match=expected_match_pattern):
            S3Service.upload_file(file_obj=mock_upload_file_obj)

        mock_upload_file_obj.file.seek.assert_called_once_with(0)
        captured = capsys.readouterr()
        assert f"S3 Upload Error (Generic): {generic_error_msg}" in captured.out


class TestS3ServiceDelete:
    VALID_S3_OBJECT_KEY = "uploads/resumes/cv_to_be_deleted.pdf"

    def test_delete_file_success(self, mock_boto3_s3_client, capsys):
        is_deleted = S3Service.delete_file(object_name=self.VALID_S3_OBJECT_KEY)

        assert is_deleted is True
        mock_boto3_s3_client.delete_object.assert_called_once_with(
            Bucket=settings.S3_BUCKET_NAME,
            Key=self.VALID_S3_OBJECT_KEY
        )
        captured = capsys.readouterr()
        assert f"Successfully deleted '{self.VALID_S3_OBJECT_KEY}' from S3 bucket '{settings.S3_BUCKET_NAME}'" in captured.out

    def test_delete_file_no_bucket_name_configured(self, mock_boto3_s3_client, mocker, capsys):
        mocker.patch("app.services.s3_service.S3_BUCKET_NAME", "")

        is_deleted = S3Service.delete_file(object_name=self.VALID_S3_OBJECT_KEY)

        assert is_deleted is False
        mock_boto3_s3_client.delete_object.assert_not_called()
        captured = capsys.readouterr()
        assert "S3 Delete Error: S3_BUCKET_NAME is not configured." in captured.out

    @pytest.mark.parametrize("invalid_object_key", ["", None])
    def test_delete_file_invalid_object_key_provided(
            self, mock_boto3_s3_client, invalid_object_key, capsys
    ):
        is_deleted = S3Service.delete_file(object_name=invalid_object_key)

        assert is_deleted is False
        mock_boto3_s3_client.delete_object.assert_not_called()
        captured = capsys.readouterr()
        assert "S3 Delete Error: Object name cannot be empty." in captured.out

    def test_delete_file_no_credentials_error(self, mock_boto3_s3_client, capsys):
        mock_boto3_s3_client.delete_object.side_effect = NoCredentialsError()

        is_deleted = S3Service.delete_file(object_name=self.VALID_S3_OBJECT_KEY)

        assert is_deleted is False
        mock_boto3_s3_client.delete_object.assert_called_once_with(
            Bucket=settings.S3_BUCKET_NAME, Key=self.VALID_S3_OBJECT_KEY
        )
        captured = capsys.readouterr()
        assert "S3 Delete Error: AWS credentials not available." in captured.out

    def test_delete_file_boto_client_error(self, mock_boto3_s3_client, capsys):
        error_message_detail = "The specified key does not exist."
        operation_name = "DeleteObject"
        error_code = "NoSuchKey"

        full_error_str = f"An error occurred ({error_code}) when calling the {operation_name} operation: {error_message_detail}"

        error_response = {'Error': {'Code': error_code, 'Message': error_message_detail}}
        mock_boto3_s3_client.delete_object.side_effect = ClientError(
            error_response=error_response, operation_name=operation_name
        )

        is_deleted = S3Service.delete_file(object_name=self.VALID_S3_OBJECT_KEY)

        assert is_deleted is False
        mock_boto3_s3_client.delete_object.assert_called_once_with(
            Bucket=settings.S3_BUCKET_NAME, Key=self.VALID_S3_OBJECT_KEY
        )
        captured = capsys.readouterr()
        expected_print_output = f"S3 Delete Error (ClientError): Code: {error_code}, Message: {full_error_str}"
        assert expected_print_output in captured.out

    def test_delete_file_generic_exception_during_delete(self, mock_boto3_s3_client, capsys):
        generic_error_msg = "Unforeseen cosmic ray interference!"
        mock_boto3_s3_client.delete_object.side_effect = Exception(generic_error_msg)

        is_deleted = S3Service.delete_file(object_name=self.VALID_S3_OBJECT_KEY)

        assert is_deleted is False
        mock_boto3_s3_client.delete_object.assert_called_once_with(
            Bucket=settings.S3_BUCKET_NAME, Key=self.VALID_S3_OBJECT_KEY
        )
        captured = capsys.readouterr()
        assert f"S3 Delete Error (Generic): {generic_error_msg}" in captured.out