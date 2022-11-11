import logging
import traceback

from flask import request, send_from_directory, jsonify
from flask_restful import Resource
from requests import exceptions
from docsbox import app
from docsbox.docs.tasks import process_convertion, create_tmp_file_and_get_mimetype, get_task, remove_file
from docsbox.docs.utils import remove_extension, set_options, is_valid_uuid
from docsbox.docs.via_controller import get_file_from_via  

def abort(status_code, message, request, traceback=None):
    if status_code >= 500:
        error_level = logging.CRITICAL
    elif status_code >= 400:
        error_level = logging.ERROR
    app.errlog.log(error_level, message, extra={ "request": request, "status": str(status_code) })
    response = jsonify( { "request": str(request), "status": str(status_code), "message": str(message), "traceback": str(traceback) } )
    response.status_code = status_code
    response.content_type = "application/json"
    return response

class DocumentStatusView(Resource):

    def get(self, task_id):
        """
        Returns information about task status.
        """
        response = {}
        try:
            task = get_task(task_id)
            if task:
                response["taskId"] = task.id
                if task.result:
                    if not isinstance(task.result, dict):
                        response["status"] = "failed"
                        app.errlog.log(logging.ERROR, ('{0}\nError: {1}').format(response, str(task.result)), extra={ "request": request, "status": str(500) })
                    elif task.result["has_failed"]:
                        response["status"] = "failed"
                        app.errlog.log(logging.ERROR, ('{0}\nError: {1}\n{2}').format(response, task.result["message"], task.result["traceback"]), extra={ "request": request, "status": str(500) })
                    else:
                        response["status"] = task.get_status()
                        response["fileType"] = task.result["fileType"]
                else: 
                    response["status"] = task.get_status()
            else:
                return abort(404, "Unknown task_id", request)
        except Exception as e:
            return abort(500, e, request, traceback.format_exc())
        return response

class DocumentTypeView(Resource):

    def post(self, file_id):
        """
        Requests from VIA fileservice the file with given id.
        Returns the File Mimetype
        """
        response = {}
        try:
            mimetype = request.headers.get('Content-Type')
            if mimetype == None or mimetype == "application/pdf" or mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                if request.files and "file" in request.files:
                    mimetype = create_tmp_file_and_get_mimetype(request.files["file"], request.files["file"].filename)['mimetype']
                elif file_id and is_valid_uuid(file_id):
                    r = get_file_from_via(file_id)
                    if r.status_code == 200:
                        mimetype = r.headers.get('Content-Type')
                        if mimetype == "application/pdf" or mimetype in app.config["GENERIC_MIMETYPES"]:
                            mimetype = create_tmp_file_and_get_mimetype(r, None, stream=True)['mimetype']
                    elif r.status_code == 404:
                        return abort(404, "File id was not found.", request)
                    else:
                        return abort(r.status_code, r, request)                
                else:
                    return abort(400, "No file has sent nor valid file_id given.", request)

            response["convertable"] = mimetype in app.config["CONVERTABLE_MIMETYPES"]
            if response["convertable"]:
                response["fileType"] = app.config["CONVERTABLE_MIMETYPES"][mimetype]["name"]
            else:
                if mimetype == "application/pdfa":
                    response["fileType"] = "PDF/A"
                else:
                    response["fileType"] = mimetype

        except exceptions.Timeout:
            return abort(504, "VIA service took too long to respond.", request)
        except Exception as e:
            return abort(500, e, request, traceback.format_exc())

        app.logger.log(logging.INFO, response, extra={ "request": request, "status": "200" })
        return response
             
class DocumentConvertView(Resource):

    def post(self, file_id):
        """
        Checks file mimetype and creates converting task of given file
        """
        result = {}
        try:
            mimetype = request.headers.get('Content-Type')
            if mimetype == None or mimetype == "application/pdf" or mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                if request.files and "file" in request.files:
                    filename = request.files["file"].filename
                    result = create_tmp_file_and_get_mimetype(request.files["file"], filename, delete=False)
                    mimetype = result['mimetype']
                    tmp_file = result['tmp_file']
                elif file_id and is_valid_uuid(file_id):
                    r = get_file_from_via(file_id)
                    if r.status_code == 200:
                        filename = request.headers.get('Content-Disposition')
                        mimetype = r.headers.get('Content-Type')
                        result = create_tmp_file_and_get_mimetype(r, filename, stream=True, delete=False)
                        if mimetype == "application/pdf" or mimetype in app.config["GENERIC_MIMETYPES"]:
                            mimetype = result['mimetype']
                        tmp_file = result['tmp_file']
                    elif r.status_code == 404:
                        return abort(404, "File id was not found.", request)
                    else:
                        return abort(r.status_code, r, request)
                else:
                    return abort(400, "No file has sent nor valid file_id given.", request)
                
            if mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                remove_file(tmp_file.name)
                if mimetype == "Unknown/Corrupted":
                    response = { "status": "corrupted", "fileType": mimetype }
                else:
                    response = { "status": "non-convertable", "fileType": mimetype }
            else:
                options = set_options(request.headers, mimetype)

                task = process_convertion.queue(tmp_file.name, options, 
                                                { "filename": remove_extension(filename), "mimetype": mimetype })
                response = { "taskId": task.id, "status": task.get_status() }

        except exceptions.Timeout:
            return abort(504, "VIA service took too long to respond.", request)
        except ValueError as err:
            if tmp_file:
                remove_file(tmp_file.name)
            return abort(400, err.args[0], request)
        except Exception as e:
            return abort(500, e, request, traceback.format_exc())

        app.logger.log(logging.INFO, response, extra={ "request": request, "status": "200" })
        return response

class DocumentDownloadView(Resource):

    def get(self, task_id):
        """
        If task with given id is finished saves the new converted file to Via fileservice
        and returns the respective file id
        """
        response = {}
        try:
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
                        else:
                            response= send_from_directory(app.config["MEDIA_PATH"], task.id, as_attachment=True, download_name=task.result["fileName"])
                            remove_file(app.config["MEDIA_PATH"] + task.id)
                            app.logger.log(logging.INFO, "file: %s"%(task.result["fileName"]), extra={ "request": request, "status": "200" })
                            
                    else:
                        return abort(404, "Task with no result", request)
                else:
                    return abort(400, "Task is still queued", request)
            else:
                return abort(404, "Unknown task_id", request)
        except exceptions.Timeout:
            return abort(504, "VIA service took too long to respond.", request)
        except Exception as e:
            return abort(500, e, request, traceback.format_exc())

        return response
