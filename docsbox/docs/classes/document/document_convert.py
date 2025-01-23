from flask import jsonify


class DocumentConvert:
    task_id: str
    status: str
    mime_type: str
    pdf_version: str
    file_type: str

    def serialize(self):
        document_convert = {
            "status": self.status
        }
        if hasattr(self, "task_id"):
            document_convert["taskId"] = self.task_id
        if hasattr(self, "mime_type"):
            document_convert["mimeType"] = self.mime_type
        if hasattr(self, "pdf_version"):
            document_convert["pdfVersion"] = self.pdf_version
        if hasattr(self, "file_type"):
            document_convert["fileType"] = self.file_type
        return jsonify(document_convert)
