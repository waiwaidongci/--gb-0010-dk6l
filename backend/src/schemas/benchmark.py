from pydantic import BaseModel,Field
class BenchmarkInput(BaseModel):
    code:str=Field(min_length=2,max_length=80)
    name:str=Field(min_length=2,max_length=160)
    period:str=Field(min_length=2,max_length=40)
    source_file:str=Field(min_length=2,max_length=160)
    note:str=Field(default='',max_length=600)
    csv_text:str=Field(min_length=20,max_length=1000000)
