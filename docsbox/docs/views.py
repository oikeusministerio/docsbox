import datetime
import logging

from flask import request, send_from_directory
from flask_restful import Resource, abort as flask_abort
from requests import exceptions
from docsbox import app
from docsbox.docs.tasks import process_convertion, create_tmp_file_and_get_mimetype, get_task, remove_file
from docsbox.docs.utils import remove_extension, set_options, is_valid_uuid
from docsbox.docs.via_controller import get_file_from_via  

def abort(error_code, message, request):
    if error_code >= 500:
        error_level = logging.CRITICAL
    elif error_code >= 400:
        error_level = logging.ERROR
    app.errlog.log(error_level, message, extra={ "request": request, "status": str(error_code) })
    flask_abort(error_code, message=message)

class DocumentStatusView(Resource):

    def get(self, task_id):
        """
        Returns information about task status.
        """
        task = get_task(task_id)
        if task:
            if task.result:
                return {
                    "taskId": task.id,
                    "status": task.get_status(),
                    "fileType": task.result["fileType"]
                }
            else: 
                return {
                    "taskId": task.id,
                    "status": task.get_status()
                }
        else:
            abort(404, "Unknown task_id", request)

class DocumentTypeView(Resource):

    def post(self, file_id):
        """
        Requests from VIA fileservice the file with given id.
        Returns the File Mimetype
        """
        try:
            if request.files and "file" in request.files:
                mimetype = create_tmp_file_and_get_mimetype(request.files["file"], None)['mimetype']
            elif file_id and is_valid_uuid(file_id):
                try:
                    r = get_file_from_via(file_id)

                    if r.status_code == 200:
                        mimetype = create_tmp_file_and_get_mimetype(r, None, stream=True)['mimetype']
                    elif r.status_code == 404:
                        abort(404, "File id was not found.", request)
                    else:
                        abort(r.status_code, r, request)

                except exceptions.Timeout:
                    abort(504, "VIA service took too long to respond.", request)
            else:
                abort(400, "No file has sent nor valid file_id given.", request)
        except Exception as e:
            abort(500, e, request)

        isConvertable = mimetype in app.config["CONVERTABLE_MIMETYPES"]
        if isConvertable:
            filetype = app.config["CONVERTABLE_MIMETYPES"][mimetype]["name"]
        else:
            filetype = app.config["OUTPUT_FILETYPES"][mimetype]["name"] if mimetype in app.config["OUTPUT_FILETYPES"] else mimetype
        response = { "convertable": isConvertable, "fileType": filetype }
        app.logger.log(logging.INFO, response, extra={ "request": request, "status": "200" })
        return response
             
class DocumentConvertView(Resource):

    def post(self, file_id):
        """
        Checks file mimetype and creates converting task of given file
        """
        try:
            if request.files and "file" in request.files:
                filename = remove_extension(request.files["file"].filename)
                result = create_tmp_file_and_get_mimetype(request.files["file"], filename, delete=False)
                via_allowed_users = None
            elif file_id and is_valid_uuid(file_id):
                try:
                    r = get_file_from_via(file_id)
                    if r.status_code == 200:
                        filename = remove_extension(request.headers['Content-Disposition'])
                        result = create_tmp_file_and_get_mimetype(r, filename, stream=True, delete=False)

                        if 'Via-Allowed-Users' in request.headers:
                            via_allowed_users = request.headers['Via-Allowed-Users']
                        else:
                            via_allowed_users = app.config["VIA_ALLOWED_USERS"]

                    elif r.status_code == 404:
                        abort(404, "File id was not found.", request)
                    else:
                        abort(r.status_code, r, request)
                except exceptions.Timeout:
                    abort(504, "VIA service took too long to respond.", request)
            else:
                abort(400, "No file has sent nor valid file_id given.", request)
        except Exception as e:
            abort(500, e, request)

        mimetype = result['mimetype']
        tmp_file = result['tmp_file']
            
        if mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
            remove_file(result['tmp_file'].name)
            if mimetype == "Unknown/Corrupted":
                response = { "status": "corrupted", "fileType": mimetype }
            else:
                response = { "status": "non-convertable", "fileType": mimetype }
        else:
            try:
                options = set_options(request.form.get("options", None), mimetype)
            except ValueError as err:
                remove_file(result['tmp_file'].name)
                abort(400, err.args[0], request)

            task = process_convertion.queue(tmp_file.name, options, 
                                            { "filename": filename, "mimetype": mimetype, 
                                            "via_allowed_users": via_allowed_users })
            response = { "taskId": task.id, "status": task.get_status() }
        app.logger.log(logging.INFO, response, extra={ "request": request, "status": "200" })
        return response

class DocumentDownloadView(Resource):

    def get(self, task_id):
        """
        If task with given id is finished saves the new converted file to Via fileservice
        and returns the respective file id
        """
        task = get_task(task_id)
        if task:
            if task.get_status() == "finished":
                if task.result:
                    if "fileId" in task.result:
                        response = { 
                            "taskId": task.id,
                            "status": task.get_status(),
                            "convertable": True,
                            "fileId": task.result["fileId"],
                            "fileType": task.result["fileType"],
                            "mimeType": task.result["mimeType"],
                            "fileName": task.result["fileName"],
                            "fileSize": task.result["fileSize"]
                        }
                        app.logger.log(logging.INFO, response, extra={ "request": request, "status": "200" })
                        return response
                    else:
                        try:                          
                            response= send_from_directory(app.config["MEDIA_PATH"], task.id, as_attachment=True, attachment_filename=task.result["fileName"])
                            remove_file(app.config["MEDIA_PATH"] + task.id)
                            app.logger.log(logging.INFO, "file: %s"%(task.result["fileName"]), extra={ "request": request, "status": "200" })
                        except exceptions.Timeout:
                            abort(504, "VIA service took too long to respond.", request)
                    return response
                else:
                    abort(404, "Task with no result", request)
            else:
                abort(400, "Task is still queued", request)
        else:
            abort(404, "Unknown task_id", request)
