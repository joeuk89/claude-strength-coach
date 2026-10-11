"""A token bucket that spaces Hevy writes out."""

# Hevy answers 429 after about 7 rapid writes; a burst of 3 then one write
# every 3 s keeps any 10-second window at 6 or fewer.
WRITE_BURST = 3
WRITE_INTERVAL_SECONDS = 3.0


class TokenBucket:
    """`acquire()` returns once a token is free, sleeping for it if need be.

    `clock` returns an aware datetime and `sleep` takes seconds. Time the
    bucket slept counts as elapsed even when the clock is frozen (COACH_NOW),
    so a fixed clock cannot stall it.
    """

    def __init__(self, clock, sleep, burst=WRITE_BURST, interval=WRITE_INTERVAL_SECONDS):
        self._clock = clock
        self._sleep = sleep
        self.burst = burst
        self.interval = interval
        self._tokens = float(burst)
        self._at = None

    def acquire(self):
        now = self._clock().timestamp()
        if self._at is None:
            self._at = now
        now = max(now, self._at)
        self._tokens = min(float(self.burst), self._tokens + (now - self._at) / self.interval)
        self._at = now
        if self._tokens < 1:
            wait = (1 - self._tokens) * self.interval
            self._sleep(wait)
            self._at = now + wait
            self._tokens = 1.0
        self._tokens -= 1
