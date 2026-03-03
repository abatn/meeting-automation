import boto3
from botocore.exceptions import ClientError
import os

# Configuration from environment variables
MINIO_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "minio_user")
MINIO_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "minio_password")
BUCKET_NAME = "meeting-recordings"

def main():
    """Checks if the S3 bucket exists and creates it if not."""
    s3_client = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    )

    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
        print(f"✅ Bucket '{BUCKET_NAME}' already exists.")
    except ClientError as e:
        # If a 404 error is raised, the bucket does not exist.
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            print(f" bucket '{BUCKET_NAME}' does not exist. Creating it...")
            try:
                # Minio does not require a LocationConstraint
                s3_client.create_bucket(Bucket=BUCKET_NAME)
                print(f"✅ Bucket '{BUCKET_NAME}' created successfully.")
            except ClientError as creation_error:
                print(f"❌ Error creating bucket: {creation_error}")
        else:
            print(f"❌ Error checking for bucket: {e}")

if __name__ == "__main__":
    main()
