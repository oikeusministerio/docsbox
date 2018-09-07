import ujson
import datetime
import requests

from flask import request, send_from_directory
from flask_restful import Resource, abort

from docsbox import app, rq
from docsbox.docs.tasks import process_document_convertion, upload_document, create_temp_file
from docsbox.docs.utils import get_file_mimetype

def set_options(options):
    """
    Validates options
    """
    if options:  # options validation
        options = ujson.loads(options)
        formats = options.get("formats", None)
        if not isinstance(formats, list) or not formats:
            return abort(400, message="Invalid 'formats' value")
        else:
            for fmt in formats:
                supported = (fmt in app.config["CONVERTABLE_MIMETYPES"][mimetype]["formats"])
                if not supported:
                    message = "'{0}' mimetype can't be converted to '{1}'"
                    return abort(400, message=message.format(mimetype, fmt))
        thumbnails = options.get("thumbnails", None) # check for thumbnails options on request and if they are valid
        if app.config["GENERATE_THUMBNAILS"] and thumbnails: # GENERATE_THUMBNAILS is configured as False
            if not isinstance(thumbnails, dict):
                return abort(400, message="Invalid 'thumbnails' value")
            else:
                thumbnails_size = thumbnails.get("size", None)
                if not isinstance(thumbnails_size, str) or not thumbnails_size:
                    return abort(400, message="Invalid 'size' value")
                else:
                    try:
                        (width, height) = map(
                            int, thumbnails_size.split("x"))
                    except ValueError:
                        return abort(400, message="Invalid 'size' value")
                    else:
                        options["thumbnails"]["size"] = (width, height)
    else:
        options = app.config["DEFAULT_OPTIONS"]
    return options

class DocumentStatusView(Resource):

    def get(self, task_id):
        """
        Returns information about task status.
        """
        queue = rq.get_queue()
        task = queue.fetch_job(task_id)
        if task:
            return {
                "task_id": task.id,
                "status": task.status
            }
        else:
            return abort(404, message="Unknown task_id")


class DocumentTypeView(Resource):

    def get(self, file_id):
        """
        Requests from VIA fileservice the file with given id.
        Returns the File Mimetype
        """
        file_data = requests.get(app.config["VIA_URL"]+"/"+file_id)
        
        if file_data:
            tmp_file = create_temp_file(file_data)
            mimetype = get_file_mimetype(tmp_file)
            return { "mimetype": mimetype }
        else:
            return abort(404, message="file id does not exist")


class DocumentConvertView(Resource):

    def post(self, file_id):
        """
            Requests from VIA fileservice the file with given id.
            Checks file mimetype and creates converting task.
        """
        file_data = requests.get(app.config["VIA_URL"]+"/"+file_id)
        
        if file_data:
            tmp_file = create_temp_file(file_data)
            mimetype = get_file_mimetype(tmp_file)
            if mimetype in app.config["ACCEPTED_MIMETYPES"]:
                return abort(400, message="File does not need to be converted.")
            if mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                return abort(400, message="Not supported mimetype: '{0}'".format(mimetype))

            options = set_options(request.form.get("options", None))
                
            task = process_document_convertion.queue(tmp_file.name, options, {"mimetype": mimetype})
            return { "task_id": task.id, "status": task.status}
        else: 
            return abort(400, message="file field is required")


class DocumentUploadView(Resource):

    def post(self):
        """
            Recieves file, checks file mimetype and saves original document
        """
        if "file" not in request.files:
            return abort(400, message="file field is required")
        else:
            tmp_file = create_temp_file(request.files["file"])
            mimetype = get_file_mimetype(tmp_file)
            if mimetype not in app.config["ACCEPTED_MIMETYPES"]:
                if mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                    return abort(400, message="Not supported mimetype: '{0}'".format(mimetype))
                return {
                    "message": "File cannot be uploaded needs to be converted"
                }
                
            task = upload_document.queue(tmp_file.name, app.config["ACCEPTED_MIMETYPES"][mimetype]["format"])
        return {
            "id": task.id,
            "status": task.status
        }


class DocumentDownloadView(Resource):

    def get(self, task_id):
        """
            If task with given id is finished saves the new converted file to Via fileservice
            and returns the respective file id
        """
        queue = rq.get_queue()
        task = queue.fetch_job(task_id)
        if task:
            if task.status == "finished":
                converted_file = open(app.config["MEDIA_PATH"]+ "/"+ task.result))
                file_id = requests.post(app.config["VIA_URL"]+"/saveFile", files=converted_file)
                return {"file_id": file_id}
                # return send_from_directory(app.config["MEDIA_PATH"], task.result, as_attachment=True)
            else:
                return abort(400, message="Task is still queued")
        else:
            return abort(404, message="Unknown task_id")
