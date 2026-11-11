from fastapi import APIRouter, Depends
from sqlalchemy import select
from src.config.database import get_db
from src.utils.auth import current_user
from src.models import Audit
router=APIRouter(prefix="/audit")
@router.get("")
def index(db=Depends(get_db),user=Depends(current_user)):
    return db.scalars(select(Audit).order_by(Audit.id.desc()).limit(100)).all()
