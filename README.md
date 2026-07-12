# CloudVault - Secure Cloud File Storage System

CloudVault is a modern, production-ready secure cloud file storage application built with Python, Flask, SQLite, and AWS S3. It provides user authentication, secure file uploads, dynamic presigned URLs for secure downloads, and a polished dashboard.

## Key Features
- **User Authentication:** Secure registration, login, and session management using `Flask-Login` and `Flask-Bcrypt`.
- **AWS S3 Integration:** Direct, secure file uploads to AWS S3 via `boto3`.
- **Dynamic Presigned URLs:** Secure, expiring links generated for previewing and downloading private S3 objects.
- **Advanced Secure File Sharing:** Generate secure public links for files with optional password protection, custom expiry dates, and download limits. Manage all active shares from a dedicated dashboard.
- **Storage Dashboard:** View files, search, sort (by date/name), and monitor total storage usage.
- **Activity Log & Audit History:** Comprehensive tracking of all major user actions (Logins, Uploads, Shares, Deletions) to ensure accountability and transparency.
- **Security & Validation:** Password complexity enforcement, global CSRF protection, secure HTTP headers, rate-limiting on auth routes, and strict file validation.
- **Responsive UI:** Clean, modern interface built with Bootstrap 5.

## Prerequisites
- Python 3.8+
- An AWS Account with an S3 Bucket.
- AWS IAM credentials with programmatic access to the S3 bucket.

## Installation & Setup

1. **Clone the repository and enter the directory:**
   ```bash
   git clone <repository_url>
   cd CloudVault
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration:**
   Create a `.env` file in the root directory matching the following structure. Do NOT add trailing spaces:
   ```env
   SECRET_KEY=your_super_secret_flask_key
   DATABASE_URL=sqlite:///site.db
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   AWS_REGION=us-east-1
   S3_BUCKET_NAME=your-bucket-name
   ```

## AWS S3 Setup
Ensure your AWS IAM User has the following permissions for your S3 bucket (replace `your-bucket-name`):
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:GetBucketLocation",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```
*Note: Your bucket does NOT need to be public. CloudVault generates secure presigned URLs to access private files.*

## Running the Application
```bash
python run.py
```
Open your browser and navigate to `http://127.0.0.1:5000`.

## Production Readiness
When deploying to a production WSGI server (like Gunicorn):
- Ensure `app.debug` is disabled.
- Set a strong `SECRET_KEY` in the environment.
- HTTPS/SSL should be enforced at the reverse proxy (Nginx/Apache).
- Error logs are automatically captured in `logs/cloudvault.log`.
