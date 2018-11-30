from os import environ

from flask import Flask
from flask_rq2 import RQ
from flask_restful import Api
from ordbok.flask_helper import FlaskOrdbok


app = Flask(__name__)
ordbok = FlaskOrdbok()

ordbok.init_app(app)
ordbok.load()
app.config.update(ordbok)

REDIS_URL = environ.get("REDIS_URL", app.config["REDIS_URL"])

app.config.update({
    "REDIS_URL": REDIS_URL,
    "RQ_REDIS_URL": REDIS_URL
    })

api = Api(app)
rq = RQ(app)

from docsbox.docs.views import *
    
api.add_resource(DocumentTypeView, "/conversion-service/get-file-type/<file_id>")
api.add_resource(DocumentConvertView, "/conversion-service/convert/<file_id>")
api.add_resource(DocumentStatusView, "/conversion-service/status/<task_id>")
api.add_resource(DocumentDownloadView, "/conversion-service/get-converted-file/<task_id>")
api.add_resource(DeleteTmpFiles, "/conversion-service/delete-tmp-file/<task_id>")


if __name__ == "__main__":
    ordbok.app_run(app)
