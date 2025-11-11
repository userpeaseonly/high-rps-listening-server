from tasks.task import publish_single_event

# Helper function to trigger immediate event publishing
def trigger_event_publish(event_id: int, delay: int = 0):
    """
    Trigger immediate publishing of an event.
    Can be called right after saving to database.
    
    Args:
        event_id: The outbox event ID to publish
        delay: Optional delay in seconds before publishing
    """
    if delay > 0:
        publish_single_event.apply_async(args=[event_id], countdown=delay)
    else:
        publish_single_event.delay(event_id)
