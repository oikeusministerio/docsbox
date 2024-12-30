import logging
import sys
import redis
import os
import confuse

from flask import Flask
from celery import Celery
from flask_restful import Api
from docsbox.logs import GraylogLogger
from apscheduler.schedulers.background import BackgroundScheduler
from docsbox.docs.unoconv import UnoServer

app = Flask(__name__)

config = confuse.Configuration('DCS', __name__)
config.set_file(os.path.join('docsbox', 'config', 'config.yml'))
app.config.update(config.get())
app.config.update(os.environ)

REDIS_URL = app.config["REDIS_URL"]

app.config.update({
    "REDIS_URL": REDIS_URL,
    "VIA_URL": app.config["VIA_URL"],
    "VIA_CERT_PATH": app.config["VIA_CERT_PATH"],
    "VIA_ALLOWED_USERS": app.config["VIA_ALLOWED_USERS"],
    "GRAYLOG_HOST": app.config["GRAYLOG_HOST"],
    "GRAYLOG_PORT": app.config["GRAYLOG_PORT"],
    "GRAYLOG_PATH": app.config["GRAYLOG_PATH"],
    "GRAYLOG_SOURCE": app.config["GRAYLOG_SOURCE"]
})

db = redis.Redis.from_url(REDIS_URL)
api = Api(app)

celery = Celery(app.name, backend=REDIS_URL, broker=REDIS_URL)
celery.conf.update(app.config)

is_worker = 'celery' in os.path.basename(sys.argv[0])
if app.config["GRAYLOG_HOST"]:
    app.logger = GraylogLogger(logging.getLogger("docsbox"), app.config, os.path.basename(sys.argv[1]) if is_worker else "web")
else:
    app.logger = app.logger

if not is_worker:
    # Creates a default Background Scheduler for file cleaning
    from docsbox.cleaner import cleaning_job
    sched = BackgroundScheduler()
    sched.add_job(cleaning_job, 'interval', seconds=app.config["CLEANER_JOB_INTREVAL"])
    sched.start()

from docsbox.docs.views import \
    DocumentTypeView, \
    DocumentConvertView, \
    DocumentConvertViewV2, \
    DocumentStatusView, \
    DocumentDownloadView

api.add_resource(DocumentTypeView, "/conversion-service/get-file-type/<file_id>")
api.add_resource(DocumentConvertView, "/conversion-service/convert/<file_id>")
api.add_resource(DocumentConvertViewV2, "/conversion-service/v2/convert/<file_id>")
api.add_resource(DocumentStatusView, "/conversion-service/status/<task_id>")
api.add_resource(DocumentDownloadView, "/conversion-service/get-converted-file/<task_id>")

if is_worker:
    UnoServer()

if __name__ == "__main__":
    app.run()
