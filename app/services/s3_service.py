import boto3
from botocore.exceptions import NoCredentialsError
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
            raise Exception("AWS credentials not available")
        except Exception as e:
            raise Exception(f"S3 upload error: {str(e)}")
