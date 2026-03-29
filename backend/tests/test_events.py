import pytest
from app.events.event_bus import EventBus
from app.events.event_types import EventType, Event


def test_event_bus_publish_subscribe():
    bus = EventBus()
    received = []

    def handler(event):
        received.append(event)

    bus.subscribe(EventType.THINKING, handler)
    bus.publish(Event(EventType.THINKING, {"message": "test"}, "session1"))

    assert len(received) == 1
    assert received[0].type == EventType.THINKING
    assert received[0].data["message"] == "test"


def test_event_bus_multiple_subscribers():
    bus = EventBus()
    received1, received2 = [], []

    bus.subscribe(EventType.TOOL_CALLED, lambda e: received1.append(e))
    bus.subscribe(EventType.TOOL_CALLED, lambda e: received2.append(e))
    bus.publish(Event(EventType.TOOL_CALLED, {"tool": "test"}, "session1"))

    assert len(received1) == 1
    assert len(received2) == 1
