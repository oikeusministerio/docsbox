class FileInfoException:
    has_failed = True
    message: str
    traceback: str
    status: str

    def __init__(self, message: str, traceback: str, status: str = None):
        self.message = message
        self.traceback = traceback
        self.status = status

    def to_dict(self):
        file_info_exception_dict = {
            "has_failed": self.has_failed,
            "message": self.message,
            "traceback": self.traceback
        }
        if hasattr(self, "status"):
            file_info_exception_dict["status"] = self.status
        return file_info_exception_dict
