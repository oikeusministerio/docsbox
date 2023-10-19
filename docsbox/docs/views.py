
from flask import request, send_from_directory, jsonify
from flask_restful import Resource
from docsbox import app, db
from docsbox.docs.tasks import *
from docsbox.docs.utils import *


def abort(status_code, message, request=None, extras={}, traceback=None):
    if status_code >= 500:
        error_level = logging.CRITICAL
    elif status_code >= 400:
        error_level = logging.ERROR
    app.logger.log(error_level, message, extra={**extras , "request": request, "status": str(status_code)})
    response = jsonify({"request": str(request), "status": str(status_code), "message": str(message), "traceback": str(traceback)})
    response.status_code = status_code
    response.content_type = "application/json"
    return response


class DocumentStatusView(Resource):

    @staticmethod
    def get(task_id):
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
                        app.logger.log(logging.ERROR, 'Error: %s' % str(task.result), extra={"response": response, "request": request, "status": str(500)})
                    elif task.result["has_failed"]:
                        response["status"] = task.result["status"] if "status" in task.result else "failed" 
                        response["message"] = task.result["message"]
                        app.logger.log(logging.ERROR, 'Error: %s %s' % (task.result["message"], task.result["traceback"]), extra={"response": response, "request": request, "status": str(500)})
                    else:
                        response["status"] = task.get_status()
                        response["fileType"] = task.result["fileType"]
                else: 
                    response["status"] = task.get_status()
            else:
                return abort(404, "Unknown task", request, extras={"task_id": task_id})
        except Exception as e:
            return abort(500, e, request, traceback=traceback.format_exc())
        return response


class DocumentTypeView(Resource):

    @staticmethod
    def post(file_id):
        """
        Requests from VIA fileservice the file with given id.
        Returns the File Mimetype
        """
        response = {}
        try:
            if request.files and "file" in request.files:
                mimetype = get_file_mimetype_from_data(request.files["file"], request.files["file"].filename)
            elif file_id and is_valid_uuid(file_id):
                mimetype = get_file_info(file_id, request.headers.get('Content-Disposition'))["mimetype"]
            else:
                return abort(400, "No file has sent nor valid file id given.", request)
            
            response["convertable"] = mimetype in app.config["CONVERTABLE_MIMETYPES"]
            if response["convertable"]:
                response["fileType"] = app.config["CONVERTABLE_MIMETYPES"][mimetype]["name"]
            else:
                if mimetype == "application/pdfa":
                    response["fileType"] = "PDF/A"
                else:
                    response["fileType"] = mimetype
        except VIAException as via_err:
            return abort(via_err.code, via_err.message, request, extras={"original_file_id": file_id}, traceback=traceback.format_exc())
        except Exception as e:
            return abort(500, e, request, traceback=traceback.format_exc())
        
        return response


class DocumentConvertView(Resource):

    @staticmethod
    def post(file_id):
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
                file_info = get_file_info(file_id, request.headers.get('Content-Disposition'), save_file=True)
                filename = file_info["filename"]
                mimetype = file_info["mimetype"]
                file_path = file_info["file_path"]
                save_in_via = True
            else:
                return abort(400, "No file has sent nor valid file id given.", request)

            if mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                return {"status": "corrupted" if mimetype == "Unknown/Corrupted" else "non-convertable", "fileType": mimetype}

            task = process_convertion.queue(file_path, set_options(request.headers, mimetype), {"filename": filename, "mimetype": mimetype, "file_id": file_id, "save_in_via": save_in_via})
            response = {"taskId": task.id, "status": task.get_status()}
            app.logger.log(logging.INFO, "Queued conversion with task id: %s" % task.id, request, 
                           extra={"original_filename": filename, "original_mimetype": mimetype, "original_file_id": file_id})
        except ValueError as err:
            return abort(400, err.args[0], request)
        except VIAException as viaEr:
            return abort(viaEr.code, viaEr.message, request, extras={"file_id": file_id}, traceback=traceback.format_exc())
        except Exception as e:
            return abort(500, e, request, traceback=traceback.format_exc())
        return response


class DocumentConvertViewV2(Resource):

    @staticmethod
    def post(file_id):
        """
        Creates converting task of given file
        """
        response = {}
        try:
            if request.files and "file" in request.files:
                filename = request.files["file"].filename
                file_path = store_file(request.files["file"], filename)
                mimetype = get_file_mimetype(file_path)
                task = process_convertion.queue(file_path, set_options(request.headers, mimetype), {"filename": filename, "mimetype": mimetype, "save_in_via": False})
                app.logger.log(logging.INFO, "Queued conversion with task id: %s" % task.id, request,
                               extra={"original_filename": filename, "original_mimetype": mimetype})
            elif file_id and is_valid_uuid(file_id):
                task = process_convertion_by_id.queue(file_id, dict(request.headers))
                app.logger.log(logging.INFO, "Queued conversion with task id: %s" % task.id, request,
                               extra={"original_file_id": file_id, "original_filename": request.headers.get('Content-Disposition'), "original_mimetype": request.headers.get('Content-Type')})
            else:
                return abort(400, "No file has sent nor valid file_id given.", request)
            response = {"taskId": task.id, "status": task.get_status()}
        except ValueError as err:
            return abort(400, err.args[0], request)
        except VIAException as viaEr:
            return abort(viaEr.code, viaEr.message, request, extras={"file_id": file_id}, traceback=traceback.format_exc())
        except Exception as e:
            return abort(500, e, request, traceback=traceback.format_exc())
        return response


class DocumentDownloadView(Resource):

    @staticmethod
    def get(task_id):
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
                            return abort(404, "Task result not dictionary: " + str(task.result), request, extras={"task_id": task_id})
                        elif task.result["has_failed"]:
                            return abort(404, "Task has failed: " + task.result["message"], request, extras={"task_id": task_id})
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
                        else:
                            response = send_from_directory(app.config["MEDIA_PATH"], task.id, as_attachment=True, download_name=task.result["fileName"])
                            remove_file(app.config["MEDIA_PATH"] + task.id)
                    else:
                        return abort(404, "Task with no result", request, extras={"task_id": task_id})
                else:
                    return abort(400, "Task is still queued", request, extras={"task_id": task_id})
            else:
                return abort(404, "Unknown task", request, extras={"task_id": task_id})
        except Exception as e:
            return abort(500, e, request, traceback=traceback.format_exc())

        return response


def get_file_info(file_id, filename="", save_file=False):
    file_info = {}
    if db.exists('fileId:' + file_id) == 0:
        file_info = {"file_id": file_id, "mimetype": "", "filename": filename, "datetime": datetime.now().strftime('%Y/%m/%d-%H:%M:%S')}
        if save_file:
            file_info["file_path"] = store_file_from_id(file_id, filename)
            file_info["mimetype"] = get_file_mimetype(file_info["file_path"])
        else:
            file_info["mimetype"] = get_file_mimetype_from_id(file_id, filename)   
        db.set('fileId:' + file_id, json.dumps(file_info))
    else:
        file_info = json.loads(db.get('fileId:' + file_id))
        updated = False

        if file_info["filename"] is None and filename:
           file_info["filename"] = filename
           updated = True

        if save_file and "file_path" not in file_info:
            file_info["file_path"] = store_file_from_id(file_id, filename)
            updated = True

        if updated:
           file_info["datetime"] = datetime.now().strftime('%Y/%m/%d-%H:%M:%S')
           db.set('fileId:' + file_id, json.dumps(file_info))
    return file_info
