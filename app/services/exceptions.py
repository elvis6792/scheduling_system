class DoubleBookingError(Exception):
    pass

class StaffNotFoundError(Exception):
    pass

class AmbiguousEntityError(Exception):
    def __init__(self, message, matches=None):
        super().__init__(message)
        self.matches = matches or []

class ProgramNotFoundError(Exception):
    pass

class ShiftAssignmentError(Exception):
    pass
