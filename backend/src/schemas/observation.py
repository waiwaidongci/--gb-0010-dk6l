from pydantic import BaseModel,Field
class ObservationInput(BaseModel):
    venue_code:str=Field(min_length=1,max_length=60)
    staff_hours:float=Field(gt=0,le=10000000,allow_inf_nan=False)
    energy_cost:float=Field(gt=0,le=1000000000,allow_inf_nan=False)
    visits:float=Field(ge=0,le=100000000,allow_inf_nan=False)
    programs:float=Field(ge=0,le=1000000,allow_inf_nan=False)
