from pydantic import BaseModel,Field
class VenueInput(BaseModel):
    code:str=Field(min_length=2,max_length=60)
    name:str=Field(min_length=2,max_length=140)
    district:str=Field(min_length=2,max_length=80)
    kind:str=Field(default='综合文化场馆',min_length=2,max_length=60)
