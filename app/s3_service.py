import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = None
        self.bucket_name = None

    def initialize(self):
        """Initializes the boto3 client using the current app's configuration."""
        if not self.s3_client:
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
                    aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
                    region_name=current_app.config['AWS_REGION'],
                    config=Config(signature_version='s3v4')
                )
                self.bucket_name = current_app.config['S3_BUCKET_NAME']
                logger.info(f"S3Service initialized for bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {str(e)}")
                raise

    def verify_connection(self):
        """Verifies if the configured S3 bucket is accessible."""
        self.initialize()
        if not self.bucket_name:
             return False, "Bucket name is not configured."

        try:
            # We use head_bucket to check if the bucket exists and we have permission
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True, f"Successfully connected to bucket '{self.bucket_name}'."
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '403':
                return False, f"Access denied to bucket '{self.bucket_name}' (403 Forbidden)."
            elif error_code == '404':
                return False, f"Bucket '{self.bucket_name}' does not exist (404 Not Found)."
            else:
                return False, f"ClientError verifying connection: {str(e)}"
        except NoCredentialsError:
            return False, "AWS credentials not found."
        except Exception as e:
            return False, f"Unexpected error verifying connection: {str(e)}"

    def upload_file(self, file_obj, filename, content_type=None):
        """
        Uploads a file object to the configured S3 bucket.
        """
        self.initialize()
        if not self.bucket_name:
            raise ValueError("Bucket name is not configured.")

        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type

        try:
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                filename,
                ExtraArgs=extra_args
            )
            logger.info(f"Successfully uploaded {filename} to {self.bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload {filename} to {self.bucket_name}: {str(e)}")
            return False

    def get_bucket_region(self):
        """Fetches the actual region of the bucket to ensure correct S3v4 signatures."""
        try:
            location = self.s3_client.get_bucket_location(Bucket=self.bucket_name)
            region = location.get('LocationConstraint')
            # AWS returns None for us-east-1 and 'EU' for eu-west-1
            if region is None:
                return 'us-east-1'
            elif region == 'EU':
                return 'eu-west-1'
            return region
        except Exception as e:
            logger.warning(f"Could not get bucket location: {str(e)}. Falling back to configured region.")
            return self.s3_client.meta.region_name

    def generate_presigned_url(self, filename, expiration=3600, download_filename=None):
        """
        Generates a presigned URL for downloading/previewing an S3 object.
        If download_filename is provided, it sets the content disposition to attachment.
        """
        self.initialize()
        if not self.bucket_name:
            return None

        actual_region = self.get_bucket_region()

        # Always use a dedicated client with an explicit regional endpoint_url to guarantee
        # boto3 constructs the presigned URL with the correct region (e.g. s3.ap-south-1.amazonaws.com)
        regional_endpoint = f"https://s3.{actual_region}.amazonaws.com"
        
        url_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=actual_region,
            endpoint_url=regional_endpoint,
            config=Config(signature_version='s3v4')
        )

        # Print/log the generated Bucket, Key, and Region during testing
        logger.info(f"DEBUG S3: Bucket='{self.bucket_name}', Key='{filename}', Region='{actual_region}', Endpoint='{regional_endpoint}'")
        print(f"DEBUG S3: Bucket='{self.bucket_name}', Key='{filename}', Region='{actual_region}', Endpoint='{regional_endpoint}'", flush=True)

        params = {'Bucket': self.bucket_name, 'Key': filename}
        if download_filename:
            params['ResponseContentDisposition'] = f'attachment; filename="{download_filename}"'

        try:
            response = url_client.generate_presigned_url('get_object',
                                                         Params=params,
                                                         ExpiresIn=expiration)
            logger.info(f"DEBUG S3: Generated URL: {response}")
            print(f"DEBUG S3: Generated URL: {response}", flush=True)
            return response
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL for {filename}: {str(e)}")
            return None

    def delete_file(self, filename):
        """
        Deletes an object from the S3 bucket.
        """
        self.initialize()
        if not self.bucket_name:
            return False

        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=filename)
            logger.info(f"Successfully deleted {filename} from {self.bucket_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {filename} from {self.bucket_name}: {str(e)}")
            return False

    def copy_file(self, source_key, target_key):
        """
        Copies a file within the S3 bucket to a new key.
        """
        self.initialize()
        if not self.bucket_name:
            return False
            
        try:
            copy_source = {
                'Bucket': self.bucket_name,
                'Key': source_key
            }
            self.s3_client.copy_object(CopySource=copy_source, Bucket=self.bucket_name, Key=target_key)
            logger.info(f"Successfully copied {source_key} to {target_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to copy {source_key} to {target_key}: {str(e)}")
            return False

# A single instance to be used across the application
s3_service = S3Service()
