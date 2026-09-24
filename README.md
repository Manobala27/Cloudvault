<p align="center">
  <img src="assets/banner.png" alt="CloudVault Banner" width="100%">
</p>

# ☁️ CloudVault

CloudVault is a secure cloud storage web application built with Python and Flask. It allows users to upload, organize, preview, share, and manage files through a modern web interface with enterprise-inspired features.

## 🚀 Live Demo
https://cloudvault-1-w43f.onrender.com

## ✨ Features

- 🔐 User Authentication
- 📁 Folder Management
- ☁️ File Upload & Download
- ⭐ Favorites
- 🔗 Secure File Sharing
- 🔔 Notifications
- 🖼️ Image & File Preview
- 🏷️ Tags & Labels
- 🔍 Advanced Search
- 📊 Storage Analytics Dashboard
- 🔑 API Keys
- 💾 Backup & Restore
- 📱 Responsive UI
- 🌙 Dark Mode


## 📷 Screenshots

### Home Page
<p align="center">
  <img src="screenshots/home.png" width="1000">
</p>

### Login Page
<p align="center">
  <img src="screenshots/login.png" width="1000">
</p>

### Register Page
<p align="center">
  <img src="screenshots/register.png" width="1000">
</p>

### User Dashboard
<p align="center">
  <img src="screenshots/dashboard.png" width="1000">
</p>

### Upload File
<p align="center">
  <img src="screenshots/upload.png" width="1000">
</p>

### Storage Analytics
<p align="center">
  <img src="screenshots/analytics.png" width="1000">
</p>

### Admin Dashboard
<p align="center">
  <img src="screenshots/admin-dashboard.png" width="1000">
</p>

### Admin Reports
<p align="center">
  <img src="screenshots/reports.png" width="1000">
</p>

### Security Settings
<p align="center">
  <img src="screenshots/settings.png" width="1000">
</p>

## 🛠️ Tech Stack

### Backend
- Python
- Flask
- SQLAlchemy

### Database
- PostgreSQL (Neon)

### Frontend
- HTML
- CSS
- JavaScript
- Bootstrap

### Cloud & Deployment
- AWS S3
- Render
- Gunicorn

## 📦 Deployment

- Application Hosted on Render
- Database Hosted on Neon PostgreSQL

## 📡 CloudPulse Monitoring & Log Analytics Integration

CloudVault is integrated with **CloudPulse** — an enterprise serverless real-time log analytics and monitoring platform on AWS.

```
CloudVault (Monitored Application)
   │ (HTTP POST /logs)
   ▼
CloudPulse API Gateway
   │
   ▼
Amazon SQS (LogProcessingQueue)
   │
   ▼
AWS Lambda (LogProcessorFunction)
   │
   ├──────────────────────────────┐
   ▼                              ▼
Amazon DynamoDB (Logs Storage)   Amazon SNS (AlertTopic)
   │                              │ (For ERROR / CRITICAL events)
   ▼                              ▼
CloudPulse Dashboard             Email Alert Notifications
```

### Monitored Real-Time Application Events:
1. **`FILE_UPLOAD`**: Dispatched upon file or version upload (`INFO` on success, `ERROR` on failure triggering SNS alerts).
2. **`FILE_DOWNLOAD`**: Dispatched upon standard, version, or public shared link download (`INFO`).
3. **`FILE_DELETE`**: Dispatched on soft delete (`INFO`) and permanent deletion of files/folders (`WARNING`).
4. **`FILE_SHARE`**: Dispatched when public links are generated, accessed, revoked, or expired (`INFO`).
5. **`LOGIN_SUCCESS`**: Dispatched on password login and 2FA OTP verification (`INFO`).
6. **`LOGIN_FAILURE`**: Dispatched on invalid credentials (`WARNING` for single attempt, `ERROR` for $\ge 5$ attempts).
7. **`FILE_RESTORE` / `FILE_VERSION`**: Dispatched on file/folder trash restoration or version rollback (`INFO`).

### Non-Blocking & Fault-Tolerant Architecture:
CloudVault's integration service (`app.services.cloudpulse_service.cloudpulse_service`) ensures zero operational coupling. If CloudPulse is undergoing maintenance or temporarily unreachable, CloudVault continues normal operations smoothly without user disruption.

### Environment Configuration:
```bash
CLOUDPULSE_ENABLED=true
CLOUDPULSE_API_URL=https://c2064m9sol.execute-api.ap-south-1.amazonaws.com/dev/logs
CLOUDPULSE_SERVICE_NAME=CloudVault
CLOUDPULSE_TIMEOUT=3.0
```


## 👨‍💻 Author

**Mano Bala**

GitHub:
https://github.com/Manobala27
