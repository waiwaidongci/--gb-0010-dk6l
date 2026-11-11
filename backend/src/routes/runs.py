from fastapi import APIRouter,Depends
from src.config.database import get_db
from src.utils.auth import current_user,editor
from src.schemas.run import RunInput
from src.controllers.run_controller import list_runs,create_run
router=APIRouter(prefix='/runs')
@router.get('')
def index(db=Depends(get_db),user=Depends(current_user)):return list_runs(db)
@router.post('',status_code=201)
def create(data:RunInput,db=Depends(get_db),user=Depends(editor)):return create_run(db,data)

from src.controllers.run_controller import get_run
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),user=Depends(current_user)):return get_run(db,id)
