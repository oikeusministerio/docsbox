import datetime
import logging

from flask import request, send_from_directory
from flask_restful import Resource, abort
from requests import exceptions
from docsbox import app
from docsbox.docs.tasks import process_convertion, create_tmp_file_and_get_mimetype, get_task, do_task
from docsbox.docs.utils import remove_extension, set_options, is_valid_uuid
from docsbox.docs.via_controller import get_file_from_via  

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
                    "status": task.status,
                    "fileType": task.result["fileType"]
                }
            else: 
                return {
                    "taskId": task.id,
                    "status": task.status
                }
        else:
            app.errlog.log(logging.ERROR, "Unknown task_id", extra={"request": request, "status": 404})
            abort(404, message="Unknown task_id")

class DocumentTypeView(Resource):

    def post(self, file_id):
        """
        Requests from VIA fileservice the file with given id.
        Returns the File Mimetype
        """
        if request.files and "file" in request.files:
            mimetype = create_tmp_file_and_get_mimetype(request.files["file"], None, schedule_file_del=False)['mimetype']
        elif file_id and is_valid_uuid(file_id):
            try:
                r = get_file_from_via(file_id)

                if r.status_code == 200:
                    mimetype = create_tmp_file_and_get_mimetype(r, None, stream=True, schedule_file_del=False)['mimetype']
                elif r.status_code == 404: 
                    app.errlog.log(logging.ERROR, "File id was not found.", extra={"request": request, "status": 404})
                    abort(404, message="File id was not found.")
                else:
                    app.errlog.log(logging.ERROR, r, extra={"request": request, "status": r.status_code})
                    abort(r.status_code, message=r)

            except exceptions.Timeout:
                app.errlog.log('CRITICAL', "VIA service took too long to respond.", extra={"request": request, "status": 504})
                abort(504, "VIA service took too long to respond.")
        else:
            app.errlog.log(logging.ERROR, "No file has sent nor valid file_id given.", extra={"request": request, "status": 400})
            abort(400, message="No file has sent nor valid file_id given.")

        isConvertable = mimetype not in app.config["ACCEPTED_MIMETYPES"] and mimetype in app.config["CONVERTABLE_MIMETYPES"]
        if isConvertable:
            filetype = app.config["CONVERTABLE_MIMETYPES"][mimetype]["name"]
        else:
            filetype = app.config["ACCEPTED_MIMETYPES"][mimetype]["name"] if mimetype in app.config["ACCEPTED_MIMETYPES"] else "Unknown"
        response= { "convertable": isConvertable, "fileType": filetype }
        app.logger.log(logging.INFO, response, extra={"request": request, "status": 200})
        return response
             
class DocumentConvertView(Resource):

    def post(self, file_id):
        """
        Checks file mimetype and creates converting task of given file
        """

        if request.files and "file" in request.files:
            filename = remove_extension(request.files["file"].filename)
            result = create_tmp_file_and_get_mimetype(request.files["file"], filename)
            via_allowed_users = None
        elif file_id and is_valid_uuid(file_id):
            try:
                r = get_file_from_via(file_id)
                if r.status_code == 200:
                    filename = remove_extension(request.headers['Content-Disposition'])
                    result = create_tmp_file_and_get_mimetype(r, filename, stream=True)

                    if 'Via-Allowed-Users' in request.headers:
                        via_allowed_users = request.headers['Via-Allowed-Users']
                    else:
                        via_allowed_users = app.config["VIA_ALLOWED_USERS"]

                elif r.status_code == 404: 
                    app.errlog.log(logging.ERROR, "File id was not found.", extra={"request": request, "status": 404})
                    abort(404, message="File id was not found.")
                else:
                    app.errlog.log(logging.ERROR, r, extra={"request": request, "status": r.status_code})
                    abort(r.status_code, message=r)
            except exceptions.Timeout:
                app.errlog.log('CRITICAL', "VIA service took too long to respond.", extra={"request": request, "status": 504})
                abort(504, "VIA service took too long to respond.")
        else:
            app.errlog.log(logging.ERROR, "No file has sent nor valid file_id given.", extra={"request": request, "status": 400})
            abort(400, message="No file has sent nor valid file_id given.")

        mimetype = result['mimetype']
        tmp_file = result['tmp_file']
        
        if mimetype in app.config["ACCEPTED_MIMETYPES"]:
            message="File does not need to be converted."
            app.errlog.log(logging.WARNING, message, extra={"request": request, "status": 400})
            abort(400, message=message)
            
        if mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
            message="Not supported mimetype: '{0}'".format(mimetype)
            app.errlog.log(logging.WARNING, message, extra={"request": request, "status": 415})
            abort(415, message=message)

        try:
            options = set_options(request.form.get("options", None), mimetype)
        except ValueError as err:
            message= err.args[0]
            app.errlog.log(logging.ERROR, message, extra={"request": request, "status": 400})
            abort(400, message=message)

        task = process_convertion.queue(tmp_file.name, options, 
                                            {"filename": filename, "mimetype": mimetype, 
                                            "via_allowed_users": via_allowed_users})
        response= { "taskId": task.id, "status": task.status}
        app.logger.log(logging.INFO, response, extra={"request": request, "status": 200})
        return response

class DocumentDownloadView(Resource):

    def get(self, task_id):
        """
        If task with given id is finished saves the new converted file to Via fileservice
        and returns the respective file id
        """
        task = get_task(task_id)
        if task:
            if task.status == "finished":
                if task.result:
                    if "fileId" in task.result:
                        response= { 
                            "taskId": task.id,
                            "status": task.status,
                            "convertable": True,
                            "fileId": task.result["fileId"],
                            "fileType": task.result["fileType"],
                            "mimeType": task.result["mimeType"],
                            "fileName": task.result["fileName"]
                        }
                        app.logger.log(logging.INFO, response, extra={"request": request, "status": 200})
                        return response
                    else:
                        try:                          
                            response= send_from_directory(app.config["MEDIA_PATH"], task.id, as_attachment=True, attachment_filename=task.result["fileName"])
                            app.logger.log(logging.INFO, "file: %s"%(task.result["fileName"]), extra={"request": request, "status": 200})
                        except exceptions.Timeout:
                            app.errlog.log('CRITICAL', "VIA service took too long to respond.", extra={"request": request, "status": 504})
                            abort(504, "VIA service took too long to respond.")
                    return response
                else:
                    app.errlog.log(logging.ERROR, "Task with no result", extra={"request": request, "status": 404})
                    abort(404, message="Task with no result")
            else:
                app.errlog.log(logging.ERROR, "Task is still queued", extra={"request": request, "status": 400})
                abort(400, message="Task is still queued")
        else:
            app.errlog.log(logging.ERROR, "Unknown task_id", extra={"request": request, "status": 404})
            abort(404, message="Unknown task_id")

class DeleteTmpFiles(Resource):

    def delete(self, task_id):
        """
        If task with given id is finished get the task if
        for deleting the temp file.
        """
        task = get_task(task_id)
        if task and task.status == "finished":
            tmp_file_remove_task_id = task.meta["tmp_file_remove_task"]
            if tmp_file_remove_task_id:
                tmp_task = get_task(tmp_file_remove_task_id)
                if tmp_task:
                    if tmp_task.status != "finished":
                        tmp_task = do_task(tmp_file_remove_task_id)
                        return tmp_task.status
                    else:
                        return 'finished'
                else:
                    app.errlog.log(logging.ERROR, "Unknown tmp_file_remove_task_id", extra={"request": request, "status": 404})
                    abort(404, message="Unknown tmp_file_remove_task_id")
            else:
                return 'finished'
        else:
            app.errlog.log(logging.ERROR, "Unknown task_id", extra={"request": request, "status": 404})
            abort(404, message="Unknown task_id")