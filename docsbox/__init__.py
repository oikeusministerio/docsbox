import sys
import redis
import os

from flask import Flask
from flask_rq2 import RQ
from flask_restful import Api
from ordbok.flask_helper import FlaskOrdbok
from docsbox.logs import GraylogLogger
from apscheduler.schedulers.background import BackgroundScheduler
from docsbox.docs.unoconv import UnoServer

app = Flask(__name__)
ordbok = FlaskOrdbok()

ordbok.init_app(app)
ordbok.load()
app.config.update(ordbok)

REDIS_URL = os.environ.get("REDIS_URL", app.config["REDIS_URL"])

app.config.update({
    "REDIS_URL": REDIS_URL,
    "RQ_REDIS_URL": REDIS_URL,
    "VIA_URL": os.environ.get("VIA_URL", app.config["VIA_URL"]),
    "VIA_CERT_PATH": os.environ.get("VIA_CERT_PATH", app.config["VIA_CERT_PATH"]),
    "VIA_ALLOWED_USERS": os.environ.get("VIA_ALLOWED_USERS", app.config["VIA_ALLOWED_USERS"]),
    "GRAYLOG_HOST": os.environ.get("GRAYLOG_HOST", app.config["GRAYLOG_HOST"]),
    "GRAYLOG_PORT": os.environ.get("GRAYLOG_PORT", app.config["GRAYLOG_PORT"]),
    "GRAYLOG_PATH": os.environ.get("GRAYLOG_PATH", app.config["GRAYLOG_PATH"]),
    "GRAYLOG_SOURCE": os.environ.get("GRAYLOG_SOURCE", app.config["GRAYLOG_SOURCE"])
    })

db = redis.Redis.from_url(REDIS_URL)
api = Api(app)
rq = RQ(app)
is_worker = 'worker' in os.path.basename(sys.argv[1])
if app.config["GRAYLOG_HOST"]:
    app.logger = GraylogLogger("docsbox", app.config, os.path.basename(sys.argv[1]) if is_worker else "web" )
else:
    app.logger = app.logger

from docsbox.cleaner import cleaning_job

# Creates a default Background Scheduler for file cleaning
sched = BackgroundScheduler()
sched.add_job(cleaning_job, 'interval', seconds=app.config["CLEANER_JOB_INTREVAL"])
sched.start()

from docsbox.docs.views import *

api.add_resource(DocumentTypeView, "/conversion-service/get-file-type/<file_id>")
api.add_resource(DocumentConvertView, "/conversion-service/convert/<file_id>")
api.add_resource(DocumentStatusView, "/conversion-service/status/<task_id>")
api.add_resource(DocumentDownloadView, "/conversion-service/get-converted-file/<task_id>")
api.add_resource(DocumentConvertViewV2, "/conversion-service/v2/convert/<file_id>")

if is_worker:
    UnoServer()

if __name__ == "__main__":
    ordbok.app_run(app)
