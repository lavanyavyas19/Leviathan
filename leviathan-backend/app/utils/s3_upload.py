import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from fastapi import UploadFile
import os
import gzip
# app/utils/s3_upload.py

def upload_clean_csv_to_s3(local_path: str, bucket_name: str, s3_key: str) -> dict:
    ...

def get_s3_client():
    """Initialize S3 client with credentials from environment"""
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=os.getenv("AWS_REGION", "ap-south-1")  # Mumbai region
    )

async def upload_raw_csv_to_s3(file: UploadFile, bucket_name: str) -> dict:
    """
    Upload raw CSV file directly to existing S3 bucket.
    Compresses if not already compressed.
    Writes to: raw/uploads/...
    """
    try:
        s3_client = get_s3_client()

        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")

        await file.seek(0)
        file_content = await file.read()

        if file.filename.endswith(".csv"):
            compressed_content = gzip.compress(file_content)
            s3_key = f"raw/uploads/ais_raw_{timestamp}.csv.gz"
            content_type = "application/gzip"
        else:
            compressed_content = file_content
            s3_key = f"raw/uploads/ais_raw_{timestamp}.csv.gz"
            content_type = "application/gzip"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=compressed_content,
            ContentType=content_type
        )

        return {
            "success": True,
            "s3_key": s3_key,
            "bucket": bucket_name,
            "size_bytes": len(compressed_content),
            "message": f"File uploaded successfully to {bucket_name}/{s3_key}"
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        return {
            "success": False,
            "error": error_code,
            "error_message": str(e),
            "message": f"Failed to upload to S3: {error_code}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": "UnknownError",
            "error_message": str(e),
            "message": f"Unexpected error: {str(e)}"
        }

def upload_clean_csv_to_s3(local_path: str, bucket_name: str, s3_key: str) -> dict:
    """
    Upload a locally saved CLEAN CSV file to S3 (no compression needed).
    """
    try:
        s3_client = get_s3_client()

        if not os.path.exists(local_path):
            return {"success": False, "message": f"Clean file not found at: {local_path}"}

        with open(local_path, "rb") as f:
            body = f.read()

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=body,
            ContentType="text/csv"
        )

        return {
            "success": True,
            "bucket": bucket_name,
            "s3_key": s3_key,
            "size_bytes": len(body),
            "message": f"Clean file uploaded to {bucket_name}/{s3_key}"
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        return {
            "success": False,
            "error": error_code,
            "error_message": str(e),
            "message": f"Failed to upload clean file to S3: {error_code}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": "UnknownError",
            "error_message": str(e),
            "message": f"Unexpected error: {str(e)}"
        }
