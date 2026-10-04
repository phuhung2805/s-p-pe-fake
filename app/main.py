import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from app.config import settings
from app.database import engine, Base
import app.models  # Ensure all models are registered

# Create database tables
Base.metadata.create_all(bind=engine)

# Import module routers
from app.modules.auth.router import router as auth_router
from app.modules.shop.router import router as shop_router
from app.modules.shipper.router import router as shipper_router
from app.modules.buyer.router import router as buyer_router
from app.modules.order.router import router as order_router
from app.modules.escrow.router import router as escrow_router
from app.modules.discovery.router import router as discovery_router
from app.modules.dispute.router import router as dispute_router
from app.modules.review.router import router as review_router
from app.modules.admin.router import router as admin_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="""
    ## Secure Multi-Vendor E-Commerce Platform with End-to-End Anti-Tamper Packaging & Escrow Verification
    
    ### Key Security Innovations:
    1. **Dynamic Anti-Tamper QR Tokenization**: Cryptographically sealed using HMAC-SHA256 (order_id + shop_secret + timestamp + salt).
    2. **4-Party RBAC Handshake**: Admin, Shop, Shipper, Buyer validation.
    3. **Automated Escrow Fund Release**: Money is held in EscrowWallets and released ONLY upon valid buyer camera QR verification.
    4. **Supply Chain Fraud Defense**: Immediate dispute freeze, fraud score penalty, and privacy-masked shipping waybills.
    """
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Register all 10 sub-module routers
app.include_router(auth_router)
app.include_router(shop_router)
app.include_router(shipper_router)
app.include_router(buyer_router)
app.include_router(order_router)
app.include_router(escrow_router)
app.include_router(discovery_router)
app.include_router(dispute_router)
app.include_router(review_router)
app.include_router(admin_router)

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return HTMLResponse("<h1>Secure E-Commerce Platform API is running! Check /docs for Swagger UI.</h1>")

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "platform": settings.PROJECT_NAME,
        "version": settings.PROJECT_VERSION
    }

@app.get("/api/config")
def public_config():
    """Public runtime configuration consumed by the web client (no secrets)."""
    return {
        "site_name": settings.SITE_NAME,
        "environment": settings.ENVIRONMENT,
        "demo_mode": settings.SEED_DEMO_DATA,
        "default_location": {
            "lat": settings.DEFAULT_LATITUDE,
            "lon": settings.DEFAULT_LONGITUDE,
        },
        "recaptcha_site_key": settings.CAPTCHA_SITE_KEY if settings.CAPTCHA_ENABLED else None,
    }
