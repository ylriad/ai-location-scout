"""
main.py – application entrypoint.
Run with:  python main.py
Or:        uvicorn app.main:app --reload
"""

import uvicorn
import os

if __name__ == "__main__":
    # Render, Heroku and Railway inject a global PORT environment variable.
    # If not present, we default dynamically to 8000 for local runs.
    port = int(os.environ.get("PORT", 8000))
    
    # We strip live reload in production to bypass memory bloat watchdog errors.
    is_dev = os.environ.get("ENVIRONMENT", "dev") == "dev"
    
    uvicorn.run(
        "app.main:app",
        host      = "0.0.0.0",
        port      = port,
        reload    = is_dev,
        log_level = "info",
        # Behind Render / nginx the real client IP is in X-Forwarded-For.
        proxy_headers        = True,
        forwarded_allow_ips  = "*",
    )
