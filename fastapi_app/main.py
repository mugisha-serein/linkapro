from fastapi import FastAPI
from fastapi_app.routers import marketplace

app = FastAPI(title="Event Planning Marketplace API", version="1.0")
app.include_router(marketplace.router, prefix="/api/v1/marketplace")