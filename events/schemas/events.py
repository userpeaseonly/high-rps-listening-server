from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Union, Annotated, Literal
from datetime import datetime

from events.schemas.verify_mode import VerifyMode


class HeartbeatInfo(BaseModel):
    date_time: datetime = Field(alias="dateTime", description="Alarm triggered time in ISO 8601 format.")
    active_post_count: int = Field(alias="activePostCount", description="Number of times that the same alarm has been triggered.")
    event_type: Literal["heartBeat"] = Field(alias="eventType", description='Event type. Expected to be "heartBeat".')
    event_state: str = Field(alias="eventState", description='Durative alarm/event status: "active" or "inactive".')
    event_description: str = Field(alias="eventDescription", description='Event description, expected to be "Heartbeat".')
    
    model_config = ConfigDict(extra='ignore')



class EventNotificationAlert(BaseModel):
    date_time: datetime = Field(alias="dateTime", description="Alarm triggered time in ISO 8601 format.")
    active_post_count: int = Field(alias="activePostCount", description="Number of times that the same alarm has been triggered.")
    event_type: Literal["AccessControllerEvent"] = Field(alias="eventType", description='Event type, e.g., "accessControllerEvent".')
    event_state: str = Field(alias="eventState", description='Durative alarm/event status: "active" or "inactive".')
    event_description: str = Field(alias="eventDescription", description='Event description, e.g., "Access Controller Event".')
    device_id: str = Field(alias="deviceID", description="Device ID.")
    access_controller_event: "AccessControllerEvent" = Field(alias="AccessControllerEvent", description="Details of the access controller event.")
    
    model_config = ConfigDict(extra='ignore')


class AccessControllerEvent(BaseModel):
    major_event: int = Field(alias="majorEventType", description="Major event type.")
    minor_event: int = Field(alias="subEventType", description="Minor event type.")
    serial_no: Optional[int] = Field(alias="serialNo", default=None, description="Event serial No., which is used to check whether the event loss occurred.")
    verify_no: Optional[int] = Field(alias="verifyNo", default=None, description="Multiple authentication No.")
    person_id: Optional[str] = Field(alias="employeeNoString", default=None, description="Employee No. (person ID)")
    zone_type: Optional[int] = Field(alias="type", default=None, description="Zone type: 0 (instant zone), 1 (24-hour zone), 2 (delayed zone), 3 (internal zone), 4 (key zone), 5 (fire alarm zone), 6 (perimeter zone), 7 (24-hour silent zone), 8 (24-hour auxiliary zone), 9 (24-hour shock zone), 10 (emergency door open zone), 11 (emergency door closed zone), 255 (none).")
    swipe_card_type: Optional[int] = Field(alias="swipeCardType", default=None, description="Swipe card type: 0 (normal), 1 (swipe card), 2 (swipe card and password), 3 (swipe card and face), 4 (swipe card and fingerprint), 5 (swipe card and face and fingerprint), 6 (swipe card and face and password), 7 (swipe card and fingerprint and password), 8 (swipe card and face and fingerprint and password).")
    card_no: Optional[str] = Field(alias="cardNo", default=None, description="Card No.")
    card_type: Optional[int] = Field(alias="cardType", default=None, description="Card type: 1 (normal card), 2 (disability card), 3 (blocklist card), 4 (patrol card), 5 (duress card), 6 (super card), 7 (visitor card), 8 (dismiss card).")
    user_type: Optional[str] = Field(alias="userType", default=None, description='Person type: "normal" (normal person (resident)), "visitor" (visitor), "blacklist" (person in the blocklist), "administrators" (administrator).')
    current_verify_mode: Optional[VerifyMode] = Field(alias="currentVerifyMode", default=None, description='Current verification mode.')
    current_event: Optional[bool] = Field(alias="currentEvent", default=None, description="Whether it is a real-time event: true, false.")
    front_serial_no: Optional[int] = Field(alias="frontSerialNo", default=None, description="The previous event's serial No. If this field does not exist, the platform will check whether the event loss occurred according to the field serialNo. If both the serialNo and frontSerialNo are returned, the platform will check whether the event loss occurred according to both fields. It is mainly used to solve the problem that the serialNo is inconsistent after subscribing events or alarms.")
    attendance_status: Optional[str] = Field(alias="attendanceStatus", default=None, description='Attendance status: "undefined", "checkIn" (check in), "checkOut" (check out), "breakOut" (start of break), "breakIn" (end of break), "overtimeIn" (start of overtime), "overTimeOut" (end of overtime).')
    pictures_number: Optional[int] = Field(alias="picturesNumber", default=None, description="Number of pictures, if there is no picture, the value of this node is 0 or it is not returned.")
    mask: Optional[str] = Field(default=None, description="Whether the person is wearing a mask.")
    person_name: Optional[str] = Field(alias="name", default=None, description="Person name.")


EventUnion = Annotated[
    Union[HeartbeatInfo, EventNotificationAlert],
    Field(discriminator="event_type")
]