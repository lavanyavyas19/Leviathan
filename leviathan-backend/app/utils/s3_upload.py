import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from fastapi import UploadFile
import os
import gzip
import io

def get_s3_client():
    """Initialize S3 client with credentials from environment"""
    return boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'ap-south-1')  # Mumbai region
    )

async def upload_raw_csv_to_s3(file: UploadFile, raw_bucket: str, job_id: str):
    """
    Upload raw CSV file to S3 bucket under raw/ prefix.
    Compresses if not already compressed.

    Args:
        file: FastAPI UploadFile object
        raw_bucket: Target S3 bucket name (must already exist)
        job_id: Job ID for organizing files

    Returns:
        dict with upload status and S3 key
    """
    try:
        s3_client = get_s3_client()
        
        # Reset file pointer
        await file.seek(0)
        file_content = await file.read()

        if file_content is None:
            return {
                "success": False,
                "error": "EmptyFileContent",
                "error_message": "File read returned None",
                "message": "Raw upload failed: file content is None"
            }

        if not isinstance(file_content, (bytes, bytearray)):
            return {
                "success": False,
                "error": "InvalidFileContent",
                "error_message": f"Expected bytes, got {type(file_content).__name__}",
                "message": "Raw upload failed: invalid file content type"
            }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
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


async def upload_clean_csv_to_s3(file_path: str, bucket_name: str, job_id: str, original_filename: str) -> dict:
    """
    Upload cleaned/processed file to S3 bucket under clean/ prefix.

    This function supports parquet or csv outputs depending on the local file_path.
    """
    try:
        s3_client = get_s3_client()

        with open(file_path, 'rb') as f:
            file_content = f.read()

        local_name = os.path.basename(file_path)

        # Preserve parquet as parquet; gzip only if it is a csv
        if local_name.endswith(".parquet"):
            s3_key = f"clean/{job_id}/{local_name}"
            body = file_content
            content_type = "application/octet-stream"
        else:
            compressed_content = gzip.compress(file_content)
            base_name = os.path.splitext(os.path.basename(original_filename))[0]
            s3_key = f"clean/{job_id}/cleaned_{base_name}.csv.gz"
            body = compressed_content
            content_type = "application/gzip"

        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=body,
            ContentType=content_type
        )

        return {
            "success": True,
            "s3_key": s3_key,
            "bucket": bucket_name,
            "size_bytes": len(body),
            "s3_location": f"s3://{bucket_name}/{s3_key}",
            "message": f"Cleaned file uploaded successfully to {bucket_name}/{s3_key}"
        }

    except ClientError as e:
        error_code = e.response['Error']['Code']
        return {
            "success": False,
            "error": error_code,
            "error_message": str(e),
            "message": f"Failed to upload cleaned file to S3: {error_code}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": "UnknownError",
            "error_message": str(e),
            "message": f"Unexpected error: {str(e)}"
        }