import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"
backlog = 2048

# Worker processes
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
worker_connections = 1000
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 120))
keepalive = 2

# Logging
accesslog = '-' # stdout
errorlog = '-'  # stderr
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

# Process naming
proc_name = 'cloudvault'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

def pre_request(worker, req):
    worker.log.debug("%s %s" % (req.method, req.path))
