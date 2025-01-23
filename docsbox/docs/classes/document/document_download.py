from flask import jsonify


class DocumentDownload:
    task_id: str
    status: str
    convertable: bool
    file_id: str
    file_type: str
    mime_type: str
    pdf_version: str
    file_name: str
    file_size: str

    def serialize(self):
        return jsonify({
            "taskId": self.task_id,
            "status": self.status,
            "convertable": self.convertable,
            "fileId": self.file_id,
            "fileType": self.file_type,
            "mimeType": self.mime_type,
            "pdfVersion": self.pdf_version,
            "fileName": self.file_name,
            "fileSize": self.file_size
        })
