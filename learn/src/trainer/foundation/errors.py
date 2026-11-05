"""Domain errors shared by the trainer."""


class TrainerError(Exception):
    """Base class for trainer errors."""


class DataError(TrainerError):
    """The on-disk data is missing, malformed or violates an invariant."""


class NotFound(TrainerError):
    """A requested entity does not exist."""


class Conflict(TrainerError):
    """A request conflicts with the current state."""


class InvalidRequest(TrainerError):
    """A request is malformed or not valid for the current entity."""
