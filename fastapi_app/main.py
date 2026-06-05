import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_app.routers import marketplace

app = FastAPI(title="Event Planning Marketplace API", version="1.0")

# CORS Configuration
# Support both local development and production environments
def get_cors_origins():
    """
    Get allowed CORS origins from environment or use defaults.
    
    Environment variable: FASTAPI_CORS_ORIGINS (comma-separated)
    Defaults to localhost for development.
    """
    cors_origins_env = os.getenv("FASTAPI_CORS_ORIGINS", "")
    
    if cors_origins_env:
        # Custom origins provided via environment
        origins = [origin.strip() for origin in cors_origins_env.split(",")]
    else:
        # Default to development + frontend environment variable
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            frontend_url,
        ]
    
    return origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(marketplace.router, prefix="/api/v1/marketplace")