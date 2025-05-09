import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from app.config.settings import (
    AWS_ACCESS_KEY,
    AWS_SECRET_KEY,
    AWS_REGION,
    S3_BUCKET_NAME,
)
import logging

logger = logging.getLogger(__name__)


class S3Service:
    """Service for S3 operations"""

    @staticmethod
    def upload_file(file_obj, object_name: str | None = None) -> str | None:
        """
        Upload a file object to an S3 bucket.

        Args:
            file_obj: File-like object (e.g., FastAPI's UploadFile) to upload.
                      It should have a 'file' attribute (the actual stream)
                      and a 'filename' attribute.
            object_name: S3 object name (key). If not specified, file_obj.filename will be used.
                         The "uploads/" prefix will be added to this name.

        Returns:
            S3 URL if successful, otherwise raises an Exception.
        """
        if object_name is None:
            if not hasattr(file_obj, "filename") or not file_obj.filename:
                logger.error(
                    "S3 Upload Error: file_obj is missing a filename and no object_name was provided."
                )
                raise ValueError(
                    "Filename is required when object_name is not provided."
                )
            base_object_name = file_obj.filename
        else:
            base_object_name = object_name

        final_object_name = f"uploads/{base_object_name}"

        if not S3_BUCKET_NAME:
            logger.error("S3 Upload Error: S3_BUCKET_NAME is not configured.")
            print("S3 Upload Error: S3_BUCKET_NAME is not configured.")
            raise Exception("S3_BUCKET_NAME is not configured.")

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
        )

        try:
            if not hasattr(file_obj, "file") or not callable(
                getattr(file_obj.file, "seek", None)
            ):
                logger.error(
                    "S3 Upload Error: file_obj.file is not a valid seekable stream."
                )
                raise TypeError("file_obj.file must be a seekable file-like object.")

            file_obj.file.seek(0)
            s3_client.upload_fileobj(file_obj.file, S3_BUCKET_NAME, final_object_name)
            s3_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{final_object_name}"
            logger.info(
                f"Successfully uploaded {final_object_name} to S3. URL: {s3_url}"
            )
            return s3_url
        except NoCredentialsError:
            logger.error("S3 Upload Error: AWS credentials not available.")
            print("S3 Upload Error: AWS credentials not available.")
            raise Exception("AWS credentials not available")
        except ClientError as e:
            logger.error(f"S3 Upload Error (ClientError): {str(e)}", exc_info=True)
            print(f"S3 Upload Error (ClientError): {str(e)}")
            raise Exception(f"S3 upload error (ClientError): {str(e)}")
        except Exception as e:
            logger.error(f"S3 Upload Error (Generic): {str(e)}", exc_info=True)
            print(f"S3 Upload Error (Generic): {str(e)}")
            raise Exception(f"S3 upload error (Generic): {str(e)}")

    @staticmethod
    def delete_file(object_name: str) -> bool:
        """
        Delete a file from an S3 bucket based on its object name (key).

        Args:
            object_name: The S3 object name (key) of the file to delete.
                         e.g., "uploads/cv_to_delete.pdf"

        Returns:
            True if successful, False otherwise.
        """
        if not S3_BUCKET_NAME:
            logger.error("S3 Delete Error: S3_BUCKET_NAME is not configured.")
            print("S3 Delete Error: S3_BUCKET_NAME is not configured.")
            return False

        if not object_name:
            logger.error("S3 Delete Error: Object name cannot be empty.")
            print("S3 Delete Error: Object name cannot be empty.")
            return False

        s3_client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
        )
        try:
            logger.info(
                f"Attempting to delete '{object_name}' from S3 bucket '{S3_BUCKET_NAME}'"
            )
            s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=object_name)
            logger.info(
                f"Successfully deleted '{object_name}' from S3 bucket '{S3_BUCKET_NAME}'"
            )
            print(
                f"Successfully deleted '{object_name}' from S3 bucket '{S3_BUCKET_NAME}'"
            )  # For capsys
            return True
        except NoCredentialsError:
            logger.error("S3 Delete Error: AWS credentials not available.")
            print("S3 Delete Error: AWS credentials not available.")  # For capsys
            return False
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            logger.error(
                f"S3 Delete Error (ClientError): Code: {error_code}, Message: {str(e)}"
            )
            print(
                f"S3 Delete Error (ClientError): Code: {error_code}, Message: {str(e)}"
            )  # For capsys
            return False
        except Exception as e:
            logger.error(f"S3 Delete Error (Generic): {str(e)}", exc_info=True)
            print(f"S3 Delete Error (Generic): {str(e)}")  # For capsys
            return False
