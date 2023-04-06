import json

from datetime import datetime
from flask import request, send_from_directory, jsonify
from flask_restful import Resource
from requests import exceptions
from docsbox import app, db
from docsbox.docs.tasks import *
from docsbox.docs.utils import *
from docsbox.docs.via_controller import *


def abort(status_code, message, request, traceback=None):
    if status_code >= 500:
        error_level = logging.CRITICAL
    elif status_code >= 400:
        error_level = logging.ERROR
    app.errlog.log(error_level, message, extra={"request": request, "status": str(status_code)})
    response = jsonify({"request": str(request), "status": str(status_code), "message": str(message), "traceback": str(traceback)})
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
                        app.errlog.log(logging.ERROR, 'Error: %s' % str(task.result), extra={"response": response, "request": request, "status": str(500)})
                    elif task.result["has_failed"]:
                        response["status"] = "failed"
                        app.errlog.log(logging.ERROR, 'Error: %s %s' % (task.result["message"], task.result["traceback"]), extra={"response": response, "request": request, "status": str(500)})
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
            if request.files and "file" in request.files:
                mimetype = get_file_mimetype_from_data(request.files["file"])
            elif file_id and is_valid_uuid(file_id):
                mimetype = get_file_info(request, file_id)["mimetype"]
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
        except VIAException as via_err:
            return abort(via_err.code, via_err.message, request, traceback.format_exc())
        except Exception as e:
            return abort(500, e, request, traceback.format_exc())
        
        return response


class DocumentConvertView(Resource):

    def post(self, file_id):
        """
        Checks file mimetype and creates converting task of given file
        """
        response = {}
        try:
            if request.files and "file" in request.files:
                filename = request.files["file"].filename
                file_path = store_file(request.files["file"], filename)
                mimetype = get_file_mimetype(file_path)
                save_in_via = False

            elif file_id and is_valid_uuid(file_id):
                file_info = get_file_info(request, file_id)

                file_path = file_info["file_path"]
                filename = file_info["filename"]
                mimetype = file_info["mimetype"]
                save_in_via = True
            else:
                return abort(400, "No file has sent nor valid file_id given.", request)

            if mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                response = {"status": "corrupted" if mimetype == "Unknown/Corrupted" else "non-convertable", "fileType": mimetype}
            else:
                task = process_convertion.queue(file_path, set_options(request.headers, mimetype), {"filename": remove_extension(filename), "mimetype": mimetype, "save_in_via": save_in_via})
                response = {"taskId": task.id, "status": task.get_status()}
                app.logger.log(logging.INFO, "Queued conversion task %s" % task.id, extra={"request": request, "status": "200"})
        except ValueError as err:
            return abort(400, err.args[0], request)
        except VIAException as viaEr:
            return abort(viaEr.code, viaEr.message, request, traceback.format_exc())
        except Exception as e:
            return abort(500, e, request, traceback.format_exc())
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
                        if not isinstance(task.result, dict):
                            return abort(404, "Task result not dictionary: " + str(task.result), request)
                        elif task.result["has_failed"]:
                            return abort(404, "Task has failed: " + task.result["message"], request)
                        elif "fileId" in task.result:
                            response = { 
                                "taskId": task.id,
                                "status": task.get_status(),
                                "convertable": True,
                                "fileId": task.result["fileId"],
                                "fileType": task.result["fileType"],
                                "mimeType": task.result["mimeType"],
                                "fileName": task.result["fileName"],
                                "fileSize": task.result["fileSize"],
                            }
                            app.logger.log(logging.INFO, "Conversion task %s finalized" % task.id, extra={"response": response, "request": request, "status": "200"})
                        else:
                            response = send_from_directory(app.config["MEDIA_PATH"], task.id, as_attachment=True, download_name=task.result["fileName"])
                            remove_file(app.config["MEDIA_PATH"] + task.id)
                            app.logger.log(logging.INFO, "Conversion task %s finalized" % task.id, extra={"request": request, "status": "200"})
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


def get_file_info(req, file_id):
    file_info = {}
    mimetype = req.headers.get('Content-Type')
    if mimetype is None or mimetype == "application/pdf" or mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
        if db.exists('fileId:' + file_id) == 0:
            filename, tmp_file_path, mimetype = via_comunication(file_id)
            file_info = {"file_path": tmp_file_path, "mimetype": mimetype, "filename": filename, "datetime": datetime.now().strftime('%Y/%m/%d-%H:%M:%S')}
            db.set('fileId:' + file_id, json.dumps(file_info))
        else:
            file_info = json.loads(db.get('fileId:' + file_id))
            if not check_file_path(file_info["file_path"]):
                filename, tmp_file_path, mimetype = via_comunication(file_id)
                file_info = {"file_path": tmp_file_path, "mimetype": mimetype, "filename": filename, "datetime": datetime.now().strftime('%Y/%m/%d-%H:%M:%S')}
                db.set('fileId:' + file_id, json.dumps(file_info))
            elif file_info["filename"] == "" and req.headers.get('Content-Disposition'):
                file_info["filename"] = req.headers.get('Content-Disposition')
                file_info["datetime"] = datetime.now().strftime('%Y/%m/%d-%H:%M:%S')
                db.set('fileId:' + file_id, json.dumps(file_info))
    else:
        file_info["mimetype"] = mimetype
    return file_info


def via_comunication(file_id):
    try:
        via_response = get_file_from_via(file_id)
        if via_response.status_code == 200:
            filename = request.headers.get('Content-Disposition') if request.headers.get('Content-Disposition') else ""
            tmp_file_path = store_file(via_response, filename, stream=True)
            mimetype = via_response.headers.get('Content-Type')
            if mimetype is None or mimetype == "application/pdf" or mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                mimetype = get_file_mimetype(tmp_file_path)
            return filename, tmp_file_path, mimetype
        elif via_response.status_code == 404:
            raise VIAException(404, "File id was not found.")
        else:
            raise VIAException(via_response.status_code, via_response)
    except exceptions.Timeout:
        raise VIAException(504, "VIA service took too long to respond.")
