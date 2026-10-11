"""Contract between Module M2 and Module M3 (Reminder & Notification).

M2 only passes schedule_id and dose_times (NOT the whole Schedule object),
which keeps coupling low (Experiment 8 recommendation).
M3 (Himanshu) provides the real implementation; until then use the
NullReminderGateway or InMemoryReminderGateway below.
"""
from typing import Dict, List, Protocol


class ReminderGateway(Protocol):
    def register_reminders(self, schedule_id: int, dose_times: List[str]) -> None: ...
    def cancel_reminders(self, schedule_id: int) -> None: ...


class NullReminderGateway:
    """Does nothing. Default when M3 is not connected yet."""

    def register_reminders(self, schedule_id: int, dose_times: List[str]) -> None:
        return None

    def cancel_reminders(self, schedule_id: int) -> None:
        return None


class InMemoryReminderGateway:
    """Remembers calls - used by tests and the demo."""

    def __init__(self) -> None:
        self.registered: Dict[int, List[str]] = {}
        self.cancelled: List[int] = []

    def register_reminders(self, schedule_id: int, dose_times: List[str]) -> None:
        self.registered[schedule_id] = list(dose_times)

    def cancel_reminders(self, schedule_id: int) -> None:
        self.registered.pop(schedule_id, None)
        self.cancelled.append(schedule_id)
