import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.config.settings import JWT_SECRET
from src.models.user import User
bearer = HTTPBearer(auto_error=False)
def current_user(request: Request, token: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    try:
        if not token:
            raise ValueError("missing")
        claim = jwt.decode(token.credentials, JWT_SECRET, algorithms=["HS256"])
        user = db.get(User, int(claim["sub"]))
        if not user:
            raise ValueError("missing")
    except Exception:
        raise HTTPException(401, "登录已失效，请重新登录")
    request.state.actor = user.email
    return user
def editor(user=Depends(current_user)):
    if user.role not in ("admin", "analyst"):
        raise HTTPException(403, "观察员无权修改机构效率研究")
    return user
def admin(user=Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "仅评议负责人可以批准改进假设")
    return user
