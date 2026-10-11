import time
from typing import Optional

from core.contracts import VistaError


class FakeUnderstanding:
    """Test double for the external provider. Counts calls, so tests can PROVE that nothing was sent."""

    supports = frozenset({"image_understanding"})

    def __init__(self, answer="A cat on a sofa.", configured=True, error: Optional[VistaError] = None, delay=0.0):
        self.answer, self.configured, self.error, self.delay = answer, configured, error, delay
        self.calls = 0
        self.seen = None

    def is_configured(self):
        return self.configured

    def describe(self):
        return {"provider": "fake-nim", "model": "fake-vlm", "host": "example.invalid",
                "supports": ["image_understanding"]}

    def ask(self, jpeg, question, on_send=None):
        self.calls += 1
        self.seen = (jpeg, question)
        if on_send is not None:
            on_send()
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.answer
