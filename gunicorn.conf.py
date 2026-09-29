import os


bind = "0.0.0.0:8000"
workers = int(os.getenv("GUNICORN_WORKERS", "4"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
worker_class = "gthread" if threads > 1 else "sync"
accesslog = "-"
errorlog = "-"
capture_output = True
