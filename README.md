# CloudVault

CloudVault is a modern, secure, and fully-featured file storage and management platform. Designed with enterprise-grade modularity in mind, CloudVault allows users to manage, share, search, and secure their files with ease. 

## Features

- **Robust Architecture**: Built on Flask, SQLAlchemy, and AWS S3, ensuring high scalability and reliability.
- **Progressive Web App (PWA)**: Installable on Desktop/Mobile with offline shell fallback and background caching.
- **Security & 2FA**: Time-Based One-Time Password (TOTP) enforcement for accounts.
- **Public REST API**: Full programmatic access mapped to secure, SHA-256 hashed API Keys.
- **File Versioning**: Soft-deletion (Trash) combined with transparent S3-backed file versioning.
- **Advanced Sharing & Tagging**: Create secure, password-protected, and expiring links. Organize data easily using tags and favorites.
- **Backup & Restore**: Easily generate and restore JSON snapshots of your metadata without duplicating actual file storage.
- **Admin Analytics**: Live dashboards for tracking usage, API limits, overall storage, and error margins.
- **Live Search & Media Previews**: Instantly search file hierarchies and preview audio, video, images, PDFs, and code in-browser.

## Architecture

CloudVault relies on a modular 25-step execution strategy encompassing:
1. **Frontend**: Bootstrap 5 + Vanilla JS, capable of running in Dark & Light Modes seamlessly.
2. **Backend**: Python 3.11 with Flask Blueprints routing logic. 
3. **Database**: SQLAlchemy ORM for relational mapping of Users, Files, Folders, Tags, Shares, API Keys, and Backups.
4. **Storage**: Direct streams to AWS S3 (or any S3 compatible object storage like MinIO or DigitalOcean Spaces).
5. **Infrastructure**: Multi-stage Dockerized containers proxied via Nginx and managed by Gunicorn workers.

## Installation & Deployment

CloudVault is heavily container-optimized. 

### Quick Start (Docker)
1. Clone the repository.
2. Copy the environment file and edit your secrets:
   ```bash
   cp .env.example .env
   ```
3. Build and launch the stack:
   ```bash
   docker-compose up -d --build
   ```

For detailed manual instructions, HTTPS/SSL certificates, and bare-metal deployment, please refer to the [DEPLOYMENT.md](DEPLOYMENT.md).

## API & Integrations

CloudVault supports full REST endpoints authenticated via Bearer tokens. 
Generate a token in the `/settings/api-keys` dashboard. For full Swagger-like documentation, navigate to `/settings/api-keys/docs` in the live application.

## Tech Stack
- **Python 3.11**
- **Flask & Flask-Login**
- **SQLAlchemy (SQLite / PostgreSQL)**
- **Boto3 (AWS S3)**
- **Docker, Docker Compose**
- **Nginx & Gunicorn**
- **Bootstrap 5 (Frontend)**

## License
Proprietary & Confidential. All rights reserved.
