from fastapi import APIRouter,Depends,Response
from src.config.database import get_db
from src.utils.auth import current_user,editor,admin
from src.schemas.case import CaseInput
from src.controllers.case_controller import list_cases,create_case,approve_case,export_case
router=APIRouter(prefix='/cases')
@router.get('')
def index(db=Depends(get_db),user=Depends(current_user)):return list_cases(db)
@router.post('',status_code=201)
def create(data:CaseInput,db=Depends(get_db),user=Depends(editor)):return create_case(db,data)
@router.patch('/{id}/approve')
def approve(id:int,db=Depends(get_db),user=Depends(admin)):return approve_case(db,id,user)
@router.get('/{id}/export')
def export(id:int,db=Depends(get_db),user=Depends(current_user)):return Response(export_case(db,id),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="venue-case-{id}.csv"'})
