import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

load_dotenv()
RATE_LIMIT = os.getenv("RATE_LIMIT_MENSAJES", "20/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT])

def configure_settings(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[""],
        allow_credentials=True,
        allow_methods=[""],
        allow_headers=[""],
    )
    
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)