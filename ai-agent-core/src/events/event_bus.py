from typing import Callable, Dict, List
from .event_types import Event, EventType

class EventBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = {}
        return cls._instance

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]):
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)

    def publish(self, event: Event):
        if event.type in self._subscribers:
            for callback in self._subscribers[event.type]:
                callback(event)
