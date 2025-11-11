import logging
import json
from robyn import Request, exceptions, status_codes

logger = logging.getLogger(__name__)


async def extract_event_data(request: Request) -> str:
    json_string = next(
        (value for key, value in request.form_data.items() if not isinstance(value, bytearray) and "eventType" in str(value)),
        None
    )
    if not json_string:
        raise exceptions.HTTPException(status_code=status_codes.HTTP_400_BAD_REQUEST, detail="Invalid event data")
    logger.debug("Extracted JSON string: %s", json_string)
    event_data = json.loads(json_string)
    return event_data



