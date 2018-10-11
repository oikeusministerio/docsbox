import datetime
from requests import get, post

from flask import request, send_from_directory
from flask_restful import Resource, abort

from docsbox import app
from docsbox.docs.tasks import process_document_convertion, create_temp_file, get_task, do_task
from docsbox.docs.utils import get_file_mimetype, set_options, remove_extension
from docsbox.docs.via_controller import get_file_from_via, save_file_on_via  

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
            return abort(404, message="Unknown task_id")


class DocumentTypeView(Resource):

    def get(self, file_id):
        """
        Requests from VIA fileservice the file with given id.
        Returns the File Mimetype
        """

        r = get_file_from_via(file_id)

        if r.status_code == 200:
            tmp_file = create_temp_file(r)
            mimetype = get_file_mimetype(tmp_file, r.headers.get('Content-type'))
            isConvertable = mimetype not in app.config["ACCEPTED_MIMETYPES"] and mimetype in app.config["CONVERTABLE_MIMETYPES"]
            return { "convertable": isConvertable, "fileType": mimetype }
        else: 
            return abort(r.status_code, message=r.json()["message"])


class DocumentConvertView(Resource):

    def post(self, file_id):
        """
            Requests from VIA fileservice the file with given id.
            Checks file mimetype and creates converting task.
        """

        r = get_file_from_via(file_id)

        if r.status_code == 200:
            tmp_file = create_temp_file(r)
            mimetype = get_file_mimetype(tmp_file, r.headers.get('Content-type'))
            filename = remove_extension(request.headers['Content-Disposition'])
            if mimetype in app.config["ACCEPTED_MIMETYPES"]:
                return abort(400, message="File does not need to be converted.")
            if mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                return abort(415, message="Not supported mimetype: '{0}'".format(mimetype))
            try:
                options = set_options(request.form.get("options", None), mimetype)
            except ValueError as err:
                return abort(400, message=err.args[0])
                
            task = process_document_convertion.queue(tmp_file.name, options, {"filename": filename, "mimetype": mimetype})
            return { "taskId": task.id, "status": task.status}
        else: 
            return abort(r.status_code, message=r.json()["message"])


class DocumentDownloadView(Resource):

    def get(self, task_id):
        """
            If task with given id is finished saves the new converted file to Via fileservice
            and returns the respective file id
        """
        task = get_task(task_id)
        if task:
            if task.status == "finished":
                r = save_file_on_via(app.config["MEDIA_PATH"] + "/" + task.result["fileName"], task.result["fileType"])

                if r.status_code == 201:
                    return { 
                        "taskId": task.id,
                        "status": task.status,
                        "convertable": True,
                        "fileId": r.headers.get("Document-id"),
                        "fileType": task.result["fileType"],
                        "fileName": task.result["fileName"]
                    }
                else:
                    return abort(r.status_code, message=r.json()["message"])
            else:
                return abort(400, message="Task is still queued")
        else:
            return abort(404, message="Unknown task_id")


class DeleteTmpFiles(Resource):

    def delete(self, task_id):
        """
            If task with given id is finished get the task if
            for deleting the temp file.
        """
        task = get_task(task_id)
        if task and task.status == "finished":
            tmp_task_id = task.meta["tmp_file_remove_task"]
            tmp_tsk = get_task(tmp_task_id)
            if tmp_tsk.status != "finished":
                tmptask = do_task(tmp_task_id)
                return tmptask.status
            else:
                return abort(400, message="Task is " + tmp_tsk.status)
        else:
            return abort(404, message="Unknown task_id")