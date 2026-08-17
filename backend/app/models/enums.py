from enum import StrEnum


class PlanningStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class Difficulty(StrEnum):
    EASY = "easy"
    NORMAL = "normal"
    DIFFICULT = "difficult"
