# router.py
import logging
import asyncio
from robyn import SubRouter, Request, Response, exceptions, status_codes
from pydantic import TypeAdapter

from events.schemas.events import HeartbeatInfo, EventNotificationAlert, EventUnion
from events import utils, crud, models
from outbox.crud import add_to_outbox
from db import AsyncSessionLocal
from tasks.repository import _publish_event_by_id

from events.dependencies import extract_event_data

logger = logging.getLogger(__name__)

router = SubRouter(__file__, prefix="/hik")

router.inject(EXTRACT_EVENT_DATA=extract_event_data)

@router.post("/events")
async def receive_event(request: Request, router_dependencies) -> Response:
    # Extract event data using the injected dependency
    _extract_event_data = router_dependencies['EXTRACT_EVENT_DATA']

    event_data = await _extract_event_data(request)

    # Extract picture from request files
    if request.files:
        picture_name = list(request.files.keys())[0]
        picture = request.files.get(picture_name) # if you want to save the picture, you can.
    
    try:
        event = TypeAdapter(EventUnion).validate_python(event_data)
        if isinstance(event, HeartbeatInfo):
            event_in = models.Heartbeat(
                date_time=event.date_time,
                active_post_count=event.active_post_count,
                event_type=event.event_type,
                event_state=event.event_state,
                event_description=event.event_description
            )
            # async with AsyncSessionLocal() as db:
            #     saved_heartbeat = await crud.create_heartbeat(event_in, db)
            #     # Add to outbox for Kafka publishing + we don't need to publish heartbeat to kafka
            #     outbox_event = await add_to_outbox(
            #         db, 
            #         str(saved_heartbeat.id), 
            #         "Heartbeat",
            #         "heartbeat.created",
            #         event.model_dump(mode='json')  # Use mode='json' to serialize datetime
            #     )
            #     await db.commit()
                
            # logger.info(f"Heartbeat saved with ID: {outbox_event}")
            # # Publish to Kafka directly (non-blocking fire-and-forget)
            # asyncio.create_task(_publish_event_by_id(outbox_event.id))
        elif isinstance(event, EventNotificationAlert):
                utils.log_pretty_event(event)
                event_in = models.Event(
                    date_time=event.date_time,
                    active_post_count=event.active_post_count,
                    event_type=event.event_type,
                    event_state=event.event_state,
                    event_description=event.event_description,
                    device_id=event.device_id,
                    major_event=event.access_controller_event.major_event,
                    minor_event=event.access_controller_event.minor_event,
                    serial_no=event.access_controller_event.serial_no,
                    verify_no=event.access_controller_event.verify_no,
                    person_id=event.access_controller_event.person_id,
                    person_name=event.access_controller_event.person_name,
                    purpose=models.PersonPurpose.ATTENDANCE if event.access_controller_event.person_name else models.PersonPurpose.INFORMATION,
                    zone_type=event.access_controller_event.zone_type,
                    swipe_card_type=event.access_controller_event.swipe_card_type,
                    card_no=event.access_controller_event.card_no,
                    card_type=event.access_controller_event.card_type,
                    user_type=event.access_controller_event.user_type,
                    current_verify_mode=event.access_controller_event.current_verify_mode,
                    current_event=event.access_controller_event.current_event,
                    front_serial_no=event.access_controller_event.front_serial_no,
                    attendance_status=event.access_controller_event.attendance_status,
                    pictures_number=event.access_controller_event.pictures_number,
                    mask=event.access_controller_event.mask,
                    picture_url=None
                )
                async with AsyncSessionLocal() as db:
                    saved_event = await crud.create_event(event_in, db)
                    # Add to outbox for Kafka publishing if purpose is ATTENDANCE
                    if event_in.purpose == models.PersonPurpose.ATTENDANCE:
                        outbox_event = await add_to_outbox(
                            db, 
                            str(saved_event.id), 
                            "Event", 
                            "access_control.event_created",
                        event.model_dump(mode='json')  # Use mode='json' to serialize datetime
                    )
                    await db.commit()
                    
                    logger.info(f"Event saved with ID: {outbox_event}")
                    # Publish to Kafka directly (non-blocking fire-and-forget)
                    if event_in.purpose == models.PersonPurpose.ATTENDANCE:
                        asyncio.create_task(_publish_event_by_id(outbox_event.id))
        else:
            logger.warning("Received unknown event type.")
            raise exceptions.HTTPException(
                status_code=status_codes.HTTP_400_BAD_REQUEST,
                detail="Unknown event type."
            )
    except Exception as e:
        logger.error(f"Error: {e}")
        raise exceptions.HTTPException(
            status_code=status_codes.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

    return Response(status_code=status_codes.HTTP_200_OK, description="Event processed successfully.", headers={"Content-Type": "application/json"})