import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Shop, UserRole
from app.schemas import UserRegister, UserLogin, TokenResponse, UserResponse
from app.security import hash_password, verify_password, create_access_token
from app.modules.auth.dependencies import get_current_user, require_role

router = APIRouter(prefix="/api/auth", tags=["Module 1: Identity & RBAC"])

@router.post("/register", response_model=TokenResponse)
def register_user(req: UserRegister, db: Session = Depends(get_db)):
    # Check existing email
    existing_user = db.query(User).filter(User.email == req.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email is already registered")
    
    if req.role not in UserRole.ALL:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(UserRole.ALL)}")
    
    new_user = User(
        email=req.email.lower(),
        password_hash=hash_password(req.password),
        full_name=req.full_name,
        phone=req.phone,
        role=req.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # If registering as a Shop, create an initial Shop entity with a unique HMAC secret
    if req.role == UserRole.SHOP:
        shop = Shop(
            owner_id=new_user.id,
            shop_name=f"Shop của {new_user.full_name}",
            address="Hà Nội, Việt Nam",
            latitude=21.0285,
            longitude=105.8542,
            commission_rate=0.05,
            wallet_balance=0.0,
            shop_secret=secrets.token_hex(32)
        )
        db.add(shop)
        db.commit()

    token = create_access_token({"sub": str(new_user.id), "role": new_user.role, "email": new_user.email})
    return TokenResponse(
        access_token=token,
        user_id=new_user.id,
        role=new_user.role,
        email=new_user.email,
        full_name=new_user.full_name
    )

@router.post("/login", response_model=TokenResponse)
def login_user(req: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_access_token({"sub": str(user.id), "role": user.role, "email": user.email})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role,
        email=user.email,
        full_name=user.full_name
    )

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(user: User = Depends(get_current_user)):
    return user
