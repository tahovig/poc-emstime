"""Thread-safe pub/sub for run progress events.

Events are published from the background worker thread (a plain OS thread,
not a coroutine) and consumed by async SSE handlers, which bridge this
blocking queue.Queue into their event loop rather than using an
asyncio-native queue.
"""

import queue
import threading
from collections import defaultdict, deque


class ProgressBus:
    def __init__(self, history_size: int = 50):
        self._lock = threading.Lock()
        self._subscribers: dict[int, list[queue.Queue]] = defaultdict(list)
        self._history: dict[int, deque] = defaultdict(lambda: deque(maxlen=history_size))

    def publish(self, run_id: int, event: dict) -> None:
        with self._lock:
            self._history[run_id].append(event)
            subscribers = list(self._subscribers.get(run_id, ()))
        for subscriber_queue in subscribers:
            subscriber_queue.put(event)

    def subscribe(self, run_id: int) -> tuple[queue.Queue, list[dict]]:
        """Returns a fresh queue plus any buffered history, so a subscriber
        that connects mid-run doesn't miss everything published so far."""
        subscriber_queue: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers[run_id].append(subscriber_queue)
            history = list(self._history.get(run_id, ()))
        return subscriber_queue, history

    def unsubscribe(self, run_id: int, subscriber_queue: queue.Queue) -> None:
        with self._lock:
            subscribers = self._subscribers.get(run_id)
            if subscribers and subscriber_queue in subscribers:
                subscribers.remove(subscriber_queue)
            if subscribers is not None and not subscribers:
                del self._subscribers[run_id]


bus = ProgressBus()
