from fastapi import APIRouter,Depends
from src.config.database import get_db
from src.utils.auth import current_user
from src.controllers.observation_controller import list_observations
router=APIRouter(prefix='/observations')
@router.get('')
def index(benchmark_id:int,db=Depends(get_db),user=Depends(current_user)):return list_observations(db,benchmark_id)
