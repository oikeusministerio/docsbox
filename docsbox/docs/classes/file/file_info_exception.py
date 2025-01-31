from flask import jsonify


class FileInfoException:
    has_failed = True
    message: str
    traceback: str
    status: str

    def __init__(self, message: str, traceback: str, status: str = None):
        self.message = message
        self.traceback = traceback
        self.status = status

    def serialize(self):
        file_info_exception = {
            "has_failed": self.has_failed,
            "message": self.message,
            "traceback": self.traceback
        }
        if hasattr(self, "status"):
            file_info_exception["status"] = self.status
        return jsonify(file_info_exception)
