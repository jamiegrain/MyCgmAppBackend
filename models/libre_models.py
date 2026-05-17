from pydantic import BaseModel
from typing import List, Optional, Any

class Sensor(BaseModel):
    deviceId: str
    sn: str
    a: int
    w: int
    pt: int
    s: bool
    lj: bool

class AlarmRuleThreshold(BaseModel):
    on: Optional[bool] = None
    th: int
    thmm: float
    d: int
    f: Optional[float] = None
    tl: Optional[int] = None
    tlmm: Optional[float] = None

class NightDesign(BaseModel):
    i: int
    r: int
    l: int

class AlarmRules(BaseModel):
    c: bool
    h: AlarmRuleThreshold
    f: AlarmRuleThreshold
    l: AlarmRuleThreshold
    nd: NightDesign
    p: int
    r: int
    std: dict

class GlucoseMeasurement(BaseModel):
    FactoryTimestamp: str
    Timestamp: str
    type: int
    ValueInMgPerDl: int
    TrendArrow: int
    TrendMessage: Optional[str] = None
    MeasurementColor: int
    GlucoseUnits: int
    Value: float
    isHigh: bool
    isLow: bool

class FixedLowAlarmValues(BaseModel):
    mgdl: int
    mmoll: float

class PatientDevice(BaseModel):
    did: str
    dtid: int
    v: str
    ll: int
    hl: int
    u: int
    fixedLowAlarmValues: FixedLowAlarmValues
    alarms: bool
    fixedLowThreshold: int

class Connection(BaseModel):
    id: str
    patientId: str
    country: str
    status: int
    firstName: str
    lastName: str
    targetLow: int
    targetHigh: int
    uom: int
    sensor: Sensor
    alarmRules: AlarmRules
    glucoseMeasurement: GlucoseMeasurement
    glucoseItem: GlucoseMeasurement
    glucoseAlarm: Optional[Any] = None
    patientDevice: PatientDevice
    created: int

class ActiveSensorEntry(BaseModel):
    sensor: Sensor
    device: PatientDevice

class GraphEntry(BaseModel):
    FactoryTimestamp: str
    Timestamp: str
    type: int
    ValueInMgPerDl: int
    MeasurementColor: int
    GlucoseUnits: int
    Value: float
    isHigh: bool
    isLow: bool

class LibreData(BaseModel):
    connection: Connection
    activeSensors: List[ActiveSensorEntry]
    graphData: List[GraphEntry]

class AuthTicket(BaseModel):
    token: str
    expires: int
    duration: int

class LibreResponse(BaseModel):
    status: int
    data: LibreData
    ticket: AuthTicket
