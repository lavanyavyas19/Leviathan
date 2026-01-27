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

async def upload_raw_csv_to_s3(file: UploadFile, bucket_name: str, job_id: str) -> dict:
    """
    Upload raw CSV file to S3 bucket under raw/ prefix
    Compresses if not already compressed
    
    Args:
        file: FastAPI UploadFile object
        bucket_name: Target S3 bucket name (must already exist)
        job_id: Job ID for organizing files
    
    Returns:
        dict with upload status and S3 key
    """
    try:
        s3_client = get_s3_client()
        
        # Reset file pointer
        await file.seek(0)
        file_content = await file.read()
        
        # Determine filename and compression
        original_filename = file.filename or "upload.csv"
        if original_filename.endswith('.csv'):
            compressed_content = gzip.compress(file_content)
            s3_key = f"raw/{job_id}/{original_filename}.gz"
            content_type = 'application/gzip'
        else:
            # Already compressed or other format
            compressed_content = file_content
            s3_key = f"raw/{job_id}/{original_filename}"
            content_type = 'application/gzip' if original_filename.endswith('.gz') else 'text/csv'
        
        # Upload to existing bucket
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
            "s3_location": f"s3://{bucket_name}/{s3_key}",
            "message": f"File uploaded successfully to {bucket_name}/{s3_key}"
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
    Upload cleaned/processed CSV file to S3 bucket under clean/ prefix
    
    Args:
        file_path: Local path to the cleaned CSV file
        bucket_name: Target S3 bucket name (must already exist)
        job_id: Job ID for organizing files
        original_filename: Original filename for naming
    
    Returns:
        dict with upload status and S3 key
    """
    try:
        s3_client = get_s3_client()
        
        # Read the cleaned file
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Compress the cleaned file
        compressed_content = gzip.compress(file_content)
        
        # Generate cleaned filename
        base_name = os.path.splitext(os.path.basename(original_filename))[0]
        s3_key = f"clean/{job_id}/cleaned_{base_name}.csv.gz"
        
        # Upload to existing bucket
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=compressed_content,
            ContentType='application/gzip'
        )
        
        return {
            "success": True,
            "s3_key": s3_key,
            "bucket": bucket_name,
            "size_bytes": len(compressed_content),
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
