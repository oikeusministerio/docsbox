import json
import traceback
import logging

from datetime import datetime
from flask import request, send_from_directory, jsonify, Request
from docsbox.docs.classes.document import *
from docsbox.docs.classes.file import FileInfo
from flask_restful import Resource
from docsbox import app, db
from docsbox.docs.tasks import get_task, process_convertion, process_convertion_by_id, remove_file
from docsbox.docs.utils import get_file_mimetype_from_data, is_valid_uuid, store_file, get_file_mimetype, set_options, \
    store_file_from_id, get_file_mimetype_from_id
from docsbox.docs.via_controller import VIAException


def abort(status_code: int, message: Exception | str, request: Request =None, extras: dict={}, traceback: str=None):
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
    def get(task_id: str):
        """
        Returns information about task status.
        """
        response = DocumentStatus()
        try:
            task = get_task(task_id)
            if task:
                response.task_id = task.id
                if task.result:
                    if not isinstance(task.result, dict):
                        response.status = "failed"
                        app.logger.log(logging.ERROR, 'Error: %s' % str(task.result), extra={"response": response, "request": request, "status": str(500)})
                    elif task.result["has_failed"]:
                        response.status = task.result["status"] if "status" in task.result else "failed" 
                        response.message = task.result["message"]
                        app.logger.log(logging.ERROR, 'Error: %s %s' % (task.result["message"], task.result["traceback"]), extra={"response": response, "request": request, "status": str(500)})
                    else:
                        response.status = task.get_status()
                        response.file_type = task.result["fileType"]
                        response.mimetype = task.result["mimeType"]
                        response.pdf_version = task.result["pdfVersion"]
                else:
                    response.status = task.get_status()
            else:
                return abort(404, "Unknown task", request, extras={"task_id": task_id})
        except Exception as e:
            return abort(500, e, request, traceback=traceback.format_exc())

        return response.serialize()


class DocumentTypeView(Resource):

    @staticmethod
    def post(file_id: str):
        """
        Requests from VIA fileservice the file with given id.
        Returns the File Mimetype
        """
        response = DocumentType()
        try:
            if request.files and "file" in request.files:
                mimetype, version = get_file_mimetype_from_data(request.files["file"], request.files["file"].filename)
            elif file_id and is_valid_uuid(file_id):
                file_info = get_file_info(file_id, request.headers.get('Content-Disposition'))
                mimetype = file_info["mimetype"]
                version = file_info["pdf_version"]
            else:
                return abort(400, "No file was sent nor valid file id given", request)

            is_pdfa = mimetype == "application/pdf" and version
            response.convertable = not is_pdfa and mimetype in app.config["CONVERTABLE_MIMETYPES"]
            response.mime_type = mimetype
            response.pdf_version = version
            if is_pdfa:
                response.file_type = "PDF/A"
            elif response.convertable:
                response.file_type = app.config["CONVERTABLE_MIMETYPES"][mimetype]["name"]
            else:
                response.file_type = "Unknown/Corrupted"
                response.message = "The file type is not supported or the file is corrupted"
        except VIAException as via_err:
            return abort(via_err.code, via_err.message, request, extras={"original_file_id": file_id}, traceback=traceback.format_exc())
        except Exception as e:
            return abort(500, e, request, traceback=traceback.format_exc())

        return response.serialize()


class DocumentConvertView(Resource):

    @staticmethod
    def post(file_id: str):
        """
        Checks file mimetype and creates converting task of given file
        """
        response = DocumentConvert()
        try:
            version = ""
            if request.files and "file" in request.files:
                filename = request.files["file"].filename
                file_path = store_file(request.files["file"], filename)
                mimetype, version = get_file_mimetype(file_path)
                save_in_via = False
            elif file_id and is_valid_uuid(file_id):
                file_info = get_file_info(file_id, request.headers.get('Content-Disposition'), save_file=True)
                filename = file_info["filename"]
                mimetype = file_info["mimetype"]
                file_path = file_info["file_path"]
                save_in_via = True
            else:
                return abort(400, "No file has sent nor valid file id given.", request)

            options = set_options(request.headers, mimetype)
            output_pdf_version = options.get("output_pdf_version", "1")
            is_pdfa = mimetype == "application/pdf" and version
            req_same_version = mimetype == "application/pdf" and version and version[0] == output_pdf_version

            if mimetype not in app.config["CONVERTABLE_MIMETYPES"] or (mimetype == "application/pdf" and req_same_version):
                response.status = "corrupted" if mimetype == "Unknown/Corrupted" else "non-convertable"
                response.mime_type = mimetype
                response.pdf_version = version
                response.file_type = "PDF/A" if is_pdfa else "Unknown/Corrupted"
            else:
                task = process_convertion.queue(file_path, options, {"filename": filename, "mimetype": mimetype, "file_id": file_id, "save_in_via": save_in_via})
                response.task_id = task.id
                response.status = task.get_status()
                response.mime_type = mimetype
                response.pdf_version = version
                response.file_type = app.config["CONVERTABLE_MIMETYPES"][mimetype]["name"]

                app.logger.log(logging.INFO, "Queued conversion with task id: %s" % task.id, request, 
                            extra={"original_filename": filename, "original_mimetype": mimetype, "original_file_id": file_id})
        except ValueError as err:
            return abort(400, err.args[0], request)
        except VIAException as viaEr:
            return abort(viaEr.code, viaEr.message, request, extras={"file_id": file_id}, traceback=traceback.format_exc())
        except Exception as e:
            return abort(500, e, request, traceback=traceback.format_exc())

        return response.serialize()


class DocumentConvertViewV2(Resource):

    @staticmethod
    def post(file_id):
        """
        Creates converting task of given file
        """
        response = DocumentConvert()
        try:
            if request.files and "file" in request.files:
                filename = request.files["file"].filename
                file_path = store_file(request.files["file"], filename)
                mimetype, version = get_file_mimetype(file_path)

                options = set_options(request.headers, mimetype)
                output_pdf_version = options.get("output_pdf_version", "1")
                is_pdfa = mimetype == "application/pdf" and version
                req_same_version = mimetype == "application/pdf" and version and version[0] == output_pdf_version
                if mimetype not in app.config["CONVERTABLE_MIMETYPES"] or (mimetype == "application/pdf" and req_same_version):
                    response.status = "corrupted" if mimetype == "Unknown/Corrupted" else "non-convertable"
                    response.mime_type = mimetype
                    response.pdf_version = version
                    response.file_type = "PDF/A" if is_pdfa else "Unknown/Corrupted"
                    return response.serialize()


                task = process_convertion.queue(file_path, options, {"filename": filename, "mimetype": mimetype, "pdfVersion": version, "save_in_via": False})
                app.logger.log(logging.INFO, "Queued conversion with task id: %s" % task.id, request,
                               extra={"original_filename": filename, "original_mimetype": mimetype})
            elif file_id and is_valid_uuid(file_id):
                task = process_convertion_by_id.queue(file_id, dict(request.headers))
                app.logger.log(logging.INFO, "Queued conversion with task id: %s" % task.id, request,
                               extra={"original_file_id": file_id, "original_filename": request.headers.get('Content-Disposition'), "original_mimetype": request.headers.get('Content-Type')})
            else:
                return abort(400, "No file has sent nor valid file_id given.", request)
            response.task_id = task.id
            response.status = task.get_status()
        except ValueError as err:
            return abort(400, err.args[0], request)
        except VIAException as viaEr:
            return abort(viaEr.code, viaEr.message, request, extras={"file_id": file_id}, traceback=traceback.format_exc())
        except Exception as e:
            return abort(500, e, request, traceback=traceback.format_exc())

        return response.serialize()


class DocumentDownloadView(Resource):

    @staticmethod
    def get(task_id):
        """
        If task with given id is finished saves the new converted file to Via fileservice
        and returns the respective file id
        """
        response = DocumentDownload()
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
                            response.task_id = task.id
                            response.status = task.get_status()
                            response.convertable = True
                            response.file_id = task.result["fileId"]
                            response.file_type = task.result["fileType"]
                            response.mime_type = task.result["mimeType"]
                            response.pdf_version = task.result["pdfVersion"]
                            response.file_name = task.result["fileName"]
                            response.file_size = task.result["fileSize"]
                        else:
                            res = send_from_directory(app.config["MEDIA_PATH"], task.id, as_attachment=True, download_name=task.result["fileName"])
                            remove_file(app.config["MEDIA_PATH"] + task.id)
                            return res
                    else:
                        return abort(404, "Task with no result", request, extras={"task_id": task_id})
                else:
                    return abort(400, "Task is still queued", request, extras={"task_id": task_id})
            else:
                return abort(404, "Unknown task", request, extras={"task_id": task_id})
        except Exception as e:
            return abort(500, e, request, traceback=traceback.format_exc())

        return response.serialize()


def get_file_info(file_id: str, filename="", save_file=False):
    if db.exists('fileId:' + file_id) == 0:
        file_info = FileInfo(None, filename, file_id, "", None, datetime.now().strftime('%Y/%m/%d-%H:%M:%S'))
        if save_file:
            file_info.file_path = store_file_from_id(file_id, filename)
            file_info.mimetype, file_info.pdf_version = get_file_mimetype(file_info.file_path)
        else:
            file_info.mimetype, file_info.pdf_version = get_file_mimetype_from_id(file_id, filename)
        file_info_dict = file_info.__dict__
        db.set('fileId:' + file_id, json.dumps(file_info_dict))
        return file_info_dict
    else:
        file_info = json.loads(db.get('fileId:' + file_id))
        updated = False

        if file_info["filename"] is None and filename:
            file_info["filename"] = filename
            updated = True

        if save_file and ("file_path" not in file_info or file_info["file_path"] is None):
            file_info["file_path"] = store_file_from_id(file_id, filename)
            updated = True

        if updated:
            file_info["datetime"] = datetime.now().strftime('%Y/%m/%d-%H:%M:%S')
            db.set('fileId:' + file_id, json.dumps(file_info))
        return file_info
