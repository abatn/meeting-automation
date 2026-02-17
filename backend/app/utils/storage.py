import boto3
from botocore.exceptions import ClientError
from backend.app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION_NAME,
        )
        self.bucket_name = settings.S3_BUCKET_NAME

    async def upload_to_s3(self, file_object, object_name: str, content_type: str):
        """Upload a file to an S3 bucket."""
        try:
            self.s3_client.upload_fileobj(
                file_object,
                self.bucket_name,
                object_name,
                ExtraArgs={"ContentType": content_type}
            )
            logger.info(f"File {object_name} uploaded to S3 bucket {self.bucket_name}")
            return True
        except ClientError as e:
            logger.error(f"Error uploading file {object_name} to S3: {e}")
            return False

    async def get_s3_download_url(self, object_name: str, expiration: int = 3600):
        """Generate a presigned URL to share an S3 object."""
        try:
            response = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_name},
                ExpiresIn=expiration,
            )
            logger.info(f"Presigned URL generated for {object_name}")
            return response
        except ClientError as e:
            logger.error(f"Error generating presigned URL for {object_name}: {e}")
            return None

    async def delete_from_s3(self, object_name: str):
        """Delete an object from an S3 bucket."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            logger.info(f"Object {object_name} deleted from S3 bucket {self.bucket_name}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting object {object_name} from S3: {e}")
            return False

storage_service = StorageService()