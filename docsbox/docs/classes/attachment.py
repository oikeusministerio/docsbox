from typing import Any


class Attachment:
    bytes: Any
    f_props: dict
    file_spec: dict

    def __init__(self, bytes_arg, f_props: dict, file_spec: dict):
        self.bytes = bytes_arg
        self.f_props = f_props
        self.file_spec = file_spec
