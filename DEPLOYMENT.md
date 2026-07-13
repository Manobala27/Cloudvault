# CloudVault Production Deployment Guide

This document outlines the steps to deploy CloudVault into a production environment using Docker, Gunicorn, and Nginx. 

## System Requirements
- OS: Ubuntu 20.04+ (or any modern Linux distribution)
- Docker & Docker Compose v2 installed
- AWS S3 Bucket credentials (or compatible S3-like storage like MinIO or DigitalOcean Spaces)
- A domain name pointing to your server's IP address

## Environment Variables
Before starting, copy the example environment file:
```bash
cp .env.example .env
```
Open `.env` and fill in the required fields:
- `SECRET_KEY` & `WTF_CSRF_SECRET_KEY`: Generate a random string using `openssl rand -hex 32`.
- `AWS_ACCESS_KEY_ID` & `AWS_SECRET_ACCESS_KEY`: Provide your S3 keys.
- `S3_BUCKET_NAME`: The name of the bucket for file storage.
- `S3_ENDPOINT_URL`: Leave blank if using AWS. Fill out if using MinIO or Spaces (e.g., `https://nyc3.digitaloceanspaces.com`).

## Docker Deployment (Recommended)
CloudVault uses a multi-stage Docker build and is orchestrated via `docker-compose`.

1. **Build and start the services in detached mode:**
```bash
docker-compose up -d --build
```
2. **Verify the services are running:**
```bash
docker-compose ps
```
Both `cloudvault_app` (Gunicorn on Port 5000) and `cloudvault_nginx` (Nginx on Port 80) should be up and healthy.

3. **Check the health endpoint:**
Navigate to `http://<your-ip>/health` to ensure the Database and S3 connections are active.

## HTTPS Setup (Let's Encrypt)
To secure the application with HTTPS, we recommend using `certbot` alongside Nginx.

1. Ensure Nginx is exposed to the host machine via Port 80.
2. Install Certbot:
```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```
3. Run Certbot to automatically configure Nginx with SSL:
```bash
sudo certbot --nginx -d yourdomain.com
```

## Security Headers & Performance
The `nginx.conf` provided in the repository is pre-configured with:
- `X-Frame-Options` and `X-XSS-Protection` headers.
- Gzip compression for all text and UI assets.
- Explicit static asset caching to maximize the Progressive Web App (PWA) speeds.
- 50MB Upload Body sizes to prevent `413 Request Entity Too Large` errors during uploads.

## Manual Deployment (Without Docker)
If you prefer deploying bare-metal:
1. Setup a Python 3.11 virtual environment.
2. Install dependencies: `pip install -r requirements.txt`.
3. Set environment variables.
4. Run Gunicorn: `gunicorn -c gunicorn.conf.py run:app`.
5. Point your native Nginx instance at `http://localhost:5000`.
