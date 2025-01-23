class FileInfo:
    file_path: str
    filename: str
    file_id: str
    mimetype: str
    pdf_version: str
    datetime: str

    def __init__(
            self,
            file_path: str = None,
            filename: str = None,
            file_id: str = None,
            mimetype: str = None,
            pdf_version: str = None,
            datetime: str = None
    ):
        self.file_path = file_path
        self.filename = filename
        self.file_id = file_id
        self.mimetype = mimetype
        self.pdf_version = pdf_version
        self.datetime = datetime
