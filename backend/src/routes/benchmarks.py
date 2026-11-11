from fastapi import APIRouter,Depends
from src.config.database import get_db
from src.utils.auth import current_user,editor
from src.schemas.benchmark import BenchmarkInput
from src.controllers.benchmark_controller import list_benchmarks,create_benchmark
router=APIRouter(prefix='/benchmarks')
@router.get('')
def index(db=Depends(get_db),user=Depends(current_user)):return list_benchmarks(db)
@router.post('',status_code=201)
def create(data:BenchmarkInput,db=Depends(get_db),user=Depends(editor)):return create_benchmark(db,data)
