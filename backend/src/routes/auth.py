from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import User
from src.schemas.auth import LoginInput
from src.utils.security import verify_password, issue_token
from src.utils.auth import current_user
router=APIRouter(prefix="/auth")
@router.post("/login")
def login(data:LoginInput,db=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==data.email))
    if not user or not verify_password(data.password,user.password_hash):
        raise HTTPException(401,"邮箱或密码不正确")
    return {"token":issue_token(user),"user":{"id":user.id,"email":user.email,"name":user.name,"role":user.role}}
@router.get("/me")
def me(user=Depends(current_user)):
    return {"id":user.id,"email":user.email,"name":user.name,"role":user.role}
