import os
import shutil
import datetime
import subprocess

from pylokit import Office
from wand.image import Image
from tempfile import NamedTemporaryFile, TemporaryDirectory

from rq import get_current_job

from docsbox import app, rq
from docsbox.docs.utils import make_zip_archive, make_thumbnails


def get_task(task_id):
    queue = rq.get_queue()
    return queue.fetch_job(task_id)

def do_task(task_id):
    queue = rq.get_queue()
    task = queue.fetch_job(task_id)
    return queue.run_job(task)


@rq.job(timeout=app.config["REDIS_JOB_TIMEOUT"])
def remove_file(path):
    """
    Just removes a file.
    Used for deleting original files (uploaded by user) and result files (result of converting)
    """
    return os.remove(path)


def create_temp_file(original_file_data):
    with NamedTemporaryFile(delete=False, prefix=app.config["MEDIA_PATH"]) as tmp_file:
        for chunk in original_file_data.iter_content(chunk_size=128):
            tmp_file.write(chunk)
        tmp_file.flush()
        tmp_file.close()
        remove_file.schedule(
            datetime.timedelta(seconds=app.config["ORIGINAL_FILE_TTL"]), tmp_file.name)
        return tmp_file


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
    return result


def process_document_convertion(path, options, meta, current_task):
    output_path = os.path.join(app.config["MEDIA_PATH"], current_task.id)
    with Office(app.config["LIBREOFFICE_PATH"]) as office:  # acquire libreoffice lock
        with office.documentLoad(path) as original_document:  # open original document
            with TemporaryDirectory() as tmp_dir:  # create temp dir where output'll be stored
                if options["format"] in app.config[app.config["CONVERTABLE_MIMETYPES"][meta["mimetype"]]["formats"]]:
                    file_name = "{0}.{1}".format(meta["filename"], options["format"])
                    
                    if app.config["CONVERTABLE_MIMETYPES"][meta["mimetype"]]["formats"] == "PRESENTATION_EXPORT_FORMATS" and options["format"] == "pdf":
                        tmp_path=os.path.join(tmp_dir, current_task.id)
                        original_document.saveAs(tmp_path, fmt=options["format"])
                        try:
                            subprocess.check_output(app.config["GHOSTSCRIPT"] + ['-sOutputFile=' + output_path, tmp_path])
                        except:
                            current_task.cancel()
                            return
                    else:
                        original_document.saveAs(output_path, fmt=options["format"])

                    # We checks the config for the mimetype of the converted format, expect if its pdf
                    # Because in the config pdf format is as application/pdfa to diferenciate versions
                    if options["format"] == "pdf":
                        fileType="application/pdf"
                    else:
                        fileType = (key for key, value in app.config["ACCEPTED_MIMETYPES"].items() if value["format"] == options["format"])
                        
                if app.config["THUMBNAILS_GENERATE"] and options.get("thumbnails", None): # generate thumbnails
                        output_path, file_name = thumbnail_generator(path, options, meta, current_task, original_document, tmp_dir) 
        file_remove_task = remove_file.schedule(datetime.timedelta(seconds=app.config["RESULT_FILE_TTL"]), output_path)
        current_task.meta["tmp_file_remove_task"] = file_remove_task.id
        current_task.save_meta()
    return {"fileName": file_name, "fileType": fileType }


def process_image_convertion(path, options, meta, current_task):
    return "NOT IMPLEMENTED"


def process_audio_convertion(path, options, meta, current_task):
    return "NOT IMPLEMENTED"


def process_video_convertion(path, options, meta, current_task):
    return "NOT IMPLEMENTED"


def thumbnail_generator(path, options, meta, current_task, original_document, tmp_dir):
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