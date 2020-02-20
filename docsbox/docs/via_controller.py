from requests import get, post
from docsbox import app


def get_file_from_via(file_id):
    url = app.config["VIA_URL"] + "/" + file_id
    cert = app.config["VIA_CERT_PATH"]
    return get(url=url, cert=cert, stream=True, timeout=60)

def save_file_on_via(file_path, mime_type, via_allowed_users):
    with open(file_path, "rb") as data:
        cert = app.config["VIA_CERT_PATH"]
        headers = { 'VIA_ALLOWED_USERS': via_allowed_users, 'Content-type': mime_type }
        response = post(url=app.config["VIA_URL"], cert=cert, data=data, headers=headers, timeout=60)
    return response
