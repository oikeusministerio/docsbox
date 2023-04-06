import logging
import time

from requests import get, post
from docsbox import app


def get_file_from_via(file_id):
    url = app.config["VIA_URL"] + "/" + file_id
    cert = app.config["VIA_CERT_PATH"]
    return retry(lambda: get(url=url, cert=cert, stream=True, timeout=60))


def save_file_on_via(file_path, mime_type, via_allowed_users):
    with open(file_path, "rb") as data:
        cert = app.config["VIA_CERT_PATH"]
        headers = {'VIA_ALLOWED_USERS': via_allowed_users, 'Content-type': mime_type}
        response = retry(lambda: post(url=app.config["VIA_URL"], cert=cert, data=data, headers=headers, stream=True, timeout=60))
    return response


def retry(call, max_retry=int(app.config["VIA_RETRY_MAX"]), count=0):
    try:
        response = call()
        if count > 1:
            logging.warn('Retry successful on count ' + str(count))
        return response
    except Exception as e:
        if count >= max_retry:
            logging.warn('Maximum retry count exceeded, rethrowing...')
            raise e
        logging.warn('Error in VIA call, retrying... : ' + str(e))
        time.sleep(1)
        return retry(call, max_retry, count + 1)


class VIAException(Exception):
   
    def __init__(self, code, message):
        self.code = code
        self.message = message
