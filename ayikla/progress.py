"""Session-local decision pace. Never inferred from previous shoot journals."""

import math
import time
from statistics import median


class DecisionPace:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.samples = []
        self.decisions = 0
        self.last = clock()

    def restart_interval(self):
        self.last = self.clock()

    def record(self, count=1):
        now = self.clock()
        if count > 0:
            self.samples.extend([max(0, now - self.last) / count] * min(count, 101))
            self.samples = self.samples[-101:]
            self.decisions += count
        self.last = now

    def remaining(self, count):
        if self.decisions < 10 or not self.samples or count <= 0:
            return ""
        minutes = max(1, math.ceil(median(self.samples) * count / 60))
        return f" · ~{minutes} min left"

    def line(self, snapshot, mode, edit_count=0):
        if mode == "edit":
            return f"Round 2 · {edit_count} / {len(snapshot.kept)} edit picks"
        decided = len(snapshot.kept) + len(snapshot.rejected)
        return f"Round 1 · {decided} / {snapshot.total} decided" + self.remaining(len(snapshot.pending))
