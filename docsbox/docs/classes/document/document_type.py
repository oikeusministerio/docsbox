from flask import jsonify


class DocumentType:
    convertable: bool
    mime_type: str
    pdf_version: str
    file_type: str
    message: str

    def serialize(self):
        document_type = {
            "convertable": self.convertable,
            "mimeType": self.mime_type,
            "pdfVersion": self.pdf_version,
            "fileType": self.file_type
        }
        if hasattr(self, "message"):
            document_type["message"] = self.message
        return jsonify(document_type)
