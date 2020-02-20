import os
import datetime
import subprocess

from pylokit import Office
from wand.image import Image
from img2pdf import convert as imagesToPdf
from tempfile import NamedTemporaryFile, TemporaryDirectory
from rq import get_current_job
from docsbox import app, rq
from docsbox.docs.utils import make_zip_archive, make_thumbnails, get_file_mimetype
from docsbox.docs.via_controller import save_file_on_via


def get_task(task_id):
    queue = rq.get_queue()
    return queue.fetch_job(task_id)

def remove_file(path):
    """
    Just removes a file.
    Used for deleting original files (uploaded by user) and result files (result of converting)
    """
    return os.remove(path)

def create_tmp_file_and_get_mimetype(original_file, filename, stream=False, delete=True):
    result = { "mimetype": None, "tmp_file": None }
    suffix= os.path.splitext(filename)[1] if filename else None
    with NamedTemporaryFile(delete=delete, dir=app.config["MEDIA_PATH"], suffix=suffix) as tmp_file:
        if stream:
            for chunk in original_file.iter_content(chunk_size=128):
                tmp_file.write(chunk)
        else:
            original_file.save(tmp_file)
        tmp_file.flush()
        result['mimetype'] = get_file_mimetype(tmp_file)

        if delete is False:    
            result['tmp_file'] = tmp_file
    return result

@rq.job(timeout=app.config["REDIS_JOB_TIMEOUT"])
def process_convertion(path, options, meta):
    current_task = get_current_job()
    exportFormatType = app.config["CONVERTABLE_MIMETYPES"][meta["mimetype"]]["formats"]
    if exportFormatType in app.config["DOCUMENT_CONVERTION_FORMATS"]:
        result= process_document_convertion(path, options, meta, current_task)
    elif exportFormatType == "IMAGE_EXPORT_FORMATS":
        result= process_image_convertion(path, options, meta, current_task)
    elif exportFormatType == "AUDIO_EXPORT_FORMATS":
        result= process_audio_convertion(path, options, meta, current_task)
    elif exportFormatType == "VIDEO_EXPORT_FORMATS":
        result= process_video_convertion(path, options, meta, current_task)

    if result and meta["via_allowed_users"]:
        r = save_file_on_via(app.config["MEDIA_PATH"] + current_task.id, result["mimeType"], meta["via_allowed_users"])
        remove_file(app.config["MEDIA_PATH"] + current_task.id)
        result['fileId'] = r.headers.get("Document-id")
    return result

def process_document_convertion(path, options, meta, current_task):
    output_path = os.path.join(app.config["MEDIA_PATH"], current_task.id)
    with Office(app.config["LIBREOFFICE_PATH"]) as office:  # acquire libreoffice lock
        with office.documentLoad(path) as original_document:  # open original document
            if options["format"] in app.config[app.config["CONVERTABLE_MIMETYPES"][meta["mimetype"]]["formats"]]:
                file_name = "{0}.{1}".format(meta["filename"], options["format"])
                original_document.saveAs(output_path, fmt=options["format"], options="SelectPdfVersion=1")
                
                for key, value in app.config["OUTPUT_FILETYPES"].items():
                    if value["format"] == options["format"]:
                        mimetype = value["mimetype"]
                        filetype = value["name"]

                if app.config["THUMBNAILS_GENERATE"] and options.get("thumbnails", None): # generate thumbnails
                        output_path, file_name = thumbnail_generator(path, options, meta, current_task, original_document) 
    fileSize = os.path.getsize(output_path)
    remove_file(path)
    return { "fileName": file_name, "mimeType": mimetype, "fileType": filetype, "fileSize": fileSize }

def process_image_convertion(path, options, meta, current_task):
    with NamedTemporaryFile(dir=app.config["MEDIA_PATH"], suffix=".pdf") as tmp_file:
        tmp_file.write(imagesToPdf(path))
        tmp_file.flush()
        result = process_document_convertion(tmp_file, options, meta, current_task)
    return result

def process_audio_convertion(path, options, meta, current_task):
    return "NOT IMPLEMENTED"

def process_video_convertion(path, options, meta, current_task):
    return "NOT IMPLEMENTED"

def thumbnail_generator(path, options, meta, current_task, original_document):
    with TemporaryDirectory() as tmp_dir:  # create temp dir where output'll be stored
        is_created = False
        if meta["mimetype"] == "application/pdf":
            pdf_path = path
        elif "pdf" in app.config[options["formats"]]:
            pdf_path = os.path.join(tmp_dir, "pdf")
        else:
            pdf_tmp_file = NamedTemporaryFile()
            pdf_path = pdf_tmp_file.name
            original_document.saveAs(pdf_tmp_file.name, fmt="pdf")
            is_created = True
        image = Image(filename=pdf_path, resolution=app.config["THUMBNAILS_DPI"])
        if is_created:
            pdf_tmp_file.close()
        thumbnails = make_thumbnails(image, tmp_dir, options["thumbnails"]["size"])
        return make_zip_archive(current_task.id, tmp_dir) 