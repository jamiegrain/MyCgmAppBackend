from pydantic import BaseModel, Field
from typing import Optional

class GarminActivityType(BaseModel):
    typeId: int
    typeKey: str
    parentTypeId: Optional[int] = None
    isHidden: Optional[bool] = None
    restricted: Optional[bool] = None
    trimmable: Optional[bool] = None

class GarminActivity(BaseModel):
    activityId: int
    activityName: Optional[str] = None
    description: Optional[str] = None
    startTimeLocal: str
    startTimeGMT: str
    distance: Optional[float] = None
    duration: float
    elapsedDuration: Optional[float] = None
    movingDuration: Optional[float] = None
    elevationGain: Optional[float] = None
    elevationLoss: Optional[float] = None
    averageSpeed: Optional[float] = None
    maxSpeed: Optional[float] = None
    calories: Optional[float] = None
    averageHR: Optional[float] = Field(None, alias="averageHR")
    maxHR: Optional[float] = Field(None, alias="maxHR")
    avgHR: Optional[float] = Field(None, alias="avgHR")
    steps: Optional[int] = None
    activityType: GarminActivityType
    locationName: Optional[str] = None
    ownerDisplayName: Optional[str] = None
    
    class Config:
        populate_by_name = True
