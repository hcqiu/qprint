"""Request-local, throttled progress; independent of report/event retention."""
from contextvars import ContextVar
from functools import wraps
import time

OBSERVER = ContextVar("qprint_progress_observer", default=None)


class Progress:
    def __init__(self, callback):
        self.callback = callback
        self.started = time.monotonic()
        self.changed = self.started
        self.published = float("-inf")
        self.key = None

    def update(self, stage, message, *, force=False, **details):
        now = time.monotonic()
        key = (stage, message)
        if key != self.key:
            self.key, self.changed = key, now
            force = True
        if not force and now - self.published < 1:
            return
        self.published = now
        try:
            self.callback({"stage": stage, "message": message[:300], "elapsed_seconds": round(now - self.started, 1),
                           "stage_seconds": round(now - self.changed, 1), **details})
        except Exception:
            # Presentation failures must not interrupt checking or orphan its process.
            self.callback = lambda _: None


def observed():
    return OBSERVER.get() is not None


def update(stage, message, **details):
    if observer := OBSERVER.get():
        observer.update(stage, message, **details)


def with_progress(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        callback = kwargs.get("on_progress")
        if callback is None:
            return function(*args, **kwargs)
        token = OBSERVER.set(Progress(callback))
        try:
            return function(*args, **kwargs)
        finally:
            OBSERVER.reset(token)
    return wrapped
