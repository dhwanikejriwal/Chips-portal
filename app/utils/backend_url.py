from flask import current_app

def get_backend_base_url() -> str:
    """Returns the base URL of the FastAPI backend service without a trailing slash.
    In Docker: http://backend:8000
    In Local Dev: http://127.0.0.1:8000
    """
    try:
        url = current_app.config.get("BACKEND_API_URL", "http://127.0.0.1:8000/api")
    except RuntimeError:
        url = "http://127.0.0.1:8000/api"
    
    # Strip /api or trailing slashes
    if url.endswith("/api"):
        url = url[:-4]
    elif url.endswith("/api/"):
        url = url[:-5]
    return url.rstrip("/")
