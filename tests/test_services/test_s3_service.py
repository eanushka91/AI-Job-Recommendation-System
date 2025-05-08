import boto3
from botocore.exceptions import NoCredentialsError, ClientError  # Added ClientError
from app.config.settings import (
    AWS_ACCESS_KEY,
    AWS_SECRET_KEY,
    AWS_REGION,
    S3_BUCKET_NAME,
)


class S3Service:
    """Service for S3 operations"""

    @staticmethod
    def upload_file(file_obj, object_name=None):
        """
        Upload a file object to an S3 bucket

        Args:
            file_obj: File-like object to upload
            object_name: S3 object name (if not specified, file's name will be used)

        Returns:
            S3 URL if successful, None otherwise
        """
        if object_name is None:
            object_name = file_obj.filename

        # Create a prefix for better organization
        object_name = f"uploads/{object_name}"

        # Create S3 client
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
        )

        try:
            # Reset file position to beginning before uploading
            file_obj.file.seek(0)

            # Upload the file
            s3.upload_fileobj(file_obj.file, S3_BUCKET_NAME, object_name)

            # Generate and return the URL
            s3_url = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{object_name}"
            return s3_url
        except NoCredentialsError:
            # It's good practice to raise the specific error or a custom one
            # For now, following the original pattern of raising a generic Exception
            # but logging the specific cause.
            print("S3 Upload Error: AWS credentials not available")
            raise Exception("AWS credentials not available")
        except Exception as e:
            print(f"S3 Upload Error: {str(e)}")  # Log the error
            raise Exception(f"S3 upload error: {str(e)}")

    @staticmethod
    def delete_file(file_url: str):
        """
        Delete a file from an S3 bucket based on its URL.

        Args:
            file_url: The S3 URL of the file to delete.

        Returns:
            True if successful, False otherwise.
        """
        if not S3_BUCKET_NAME:
            print("S3 Delete Error: S3_BUCKET_NAME is not configured.")
            return False

        if not file_url or not file_url.startswith(
            f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/"
        ):
            print(
                f"S3 Delete Error: Invalid S3 URL or URL not from the configured bucket: {file_url}"
            )
            return False

        try:
            prefix_to_remove = f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/"
            object_name = file_url.replace(prefix_to_remove, "", 1)

            if not object_name:
                print("S3 Delete Error: Could not extract object name from URL.")
                return False

            s3 = boto3.client(
                "s3",
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY,
                region_name=AWS_REGION,
            )
            s3.delete_object(Bucket=S3_BUCKET_NAME, Key=object_name)
            print(f"Successfully deleted {object_name} from S3 bucket {S3_BUCKET_NAME}")
            return True
        except NoCredentialsError:
            print("S3 Delete Error: AWS credentials not available.")
            return False  # Silently return False as per discussion for routes
        except ClientError as e:
            # Handles S3-specific errors. delete_object usually doesn't error for "NoSuchKey".
            # But other errors like "AccessDenied" could occur.
            error_code = e.response.get("Error", {}).get("Code")
            print(
                f"S3 Delete Error (ClientError): Code: {error_code}, Message: {str(e)}"
            )
            return False
        except Exception as e:
            print(f"S3 Delete Error (Generic): {str(e)}")
            return False
