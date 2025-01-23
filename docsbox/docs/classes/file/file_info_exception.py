class FileInfoException:
    has_failed = True
    message: str
    traceback: str
    status: str

    def __init__(self, message: str, traceback: str, status: str = None):
        self.message = message
        self.traceback = traceback
        self.status = status
