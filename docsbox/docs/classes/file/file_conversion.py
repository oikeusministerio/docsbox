from typing import Any


class FileConversion:
    fileName: str
    mimeType: Any
    fileType: Any
    pdfVersion: str
    fileSize: int
    has_failed: bool

    def __init__(
            self,
            file_name: str,
            mime_type,
            file_type,
            pdf_version: str,
            file_size: int,
            has_failed = False
    ):
        self.fileName = file_name
        self.mimeType = mime_type
        self.fileType = file_type
        self.pdfVersion = pdf_version
        self.fileSize = file_size
        self.has_failed = has_failed
