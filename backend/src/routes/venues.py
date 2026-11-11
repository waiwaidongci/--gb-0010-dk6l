from fastapi import APIRouter,Depends
from src.config.database import get_db
from src.utils.auth import current_user,editor
from src.schemas.venue import VenueInput
from src.controllers.venue_controller import list_venues,create_venue
router=APIRouter(prefix='/venues')
@router.get('')
def index(db=Depends(get_db),user=Depends(current_user)):return list_venues(db)
@router.post('',status_code=201)
def create(data:VenueInput,db=Depends(get_db),user=Depends(editor)):return create_venue(db,data)
