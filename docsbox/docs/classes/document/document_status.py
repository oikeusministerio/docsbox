from flask import jsonify


class DocumentStatus:
    task_id: str
    status: str
    message: str
    file_type: str
    mimetype: str
    pdf_version: str

    def serialize(self):
        document_status = {
            "taskId": self.task_id,
            "status": self.status
        }
        if hasattr(self, "message"):
            document_status["message"] = self.message
        if hasattr(self, "file_type"):
            document_status["fileType"] = self.file_type
        if hasattr(self, "mimetype"):
            document_status["mimeType"] = self.mimetype
        if hasattr(self, "pdf_version"):
            document_status["pdfVersion"] = self.pdf_version
        return jsonify(document_status)
