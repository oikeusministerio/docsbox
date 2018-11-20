from requests import get, post
from flask import current_app as app


def get_file_from_via(file_id):
    url=app.config["VIA_URL"] + "/" + file_id
    cert=app.config["VIA_CERT_PATH"]
    return get(url=url, cert=cert, stream=True)

def save_file_on_via(file_path, file_type):
    data = open(file_path, "rb")
    cert=app.config["VIA_CERT_PATH"]
    headers = {'VIA_ALLOWED_USERS': app.config["VIA_ALLOWED_USERS"], 'Content-type': file_type}
    return post(url=app.config["VIA_URL"], cert=cert, data=data, headers=headers)
