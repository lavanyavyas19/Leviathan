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

async def upload_raw_csv_to_s3(file: UploadFile, bucket_name: str) -> dict:
    """
    Upload raw CSV file directly to existing S3 bucket
    Compresses if not already compressed
    
    Args:
        file: FastAPI UploadFile object
        bucket_name: Target S3 bucket name (must already exist)
    
    Returns:
        dict with upload status and S3 key
    """
    try:
        s3_client = get_s3_client()
        
        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        
        # Reset file pointer
        await file.seek(0)
        file_content = await file.read()
        
        # Compress if uploading plain CSV
        if file.filename.endswith('.csv'):
            compressed_content = gzip.compress(file_content)
            s3_key = f"uploads/ais_raw_{timestamp}.csv.gz"
            content_type = 'application/gzip'
        else:
            # Already compressed
            compressed_content = file_content
            s3_key = f"uploads/ais_raw_{timestamp}.csv.gz"
            content_type = 'application/gzip'
        
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
