import os
import shutil
import traceback
import json

from subprocess import run
from wand.image import Image
from img2pdf import convert as imagesToPdf
from tempfile import NamedTemporaryFile, TemporaryDirectory
from rq import get_current_job
from docsbox import app, rq
from docsbox.docs.utils import make_zip_archive, make_thumbnails, get_file_mimetype, remove_XMPMeta, check_file_content, has_PDFA_XMP, removeAlpha, correct_orientation
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
    suffix = os.path.splitext(filename)[1] if filename else ""
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
    try:
        current_task = get_current_job()
        exportFormatType = app.config["CONVERTABLE_MIMETYPES"][meta["mimetype"]]["formats"]
        if exportFormatType in app.config["DOCUMENT_CONVERTION_FORMATS"]:
            result = process_document_convertion(path, options, meta, current_task)
        elif exportFormatType == "IMAGE_EXPORT_FORMATS":
            result = process_image_convertion(path, options, meta, current_task)
        else:
            return { "has_failed": True, "message": "Conversion for {0} is not supported".format(exportFormatType)}
        if result and options["via_allowed_users"]:
            r = save_file_on_via(app.config["MEDIA_PATH"] + current_task.id, result["mimeType"], options["via_allowed_users"])
            remove_file(app.config["MEDIA_PATH"] + current_task.id)
            result['fileId'] = r.headers.get("Document-id")
        return result
    except Exception as e:
        return { "has_failed": True, "message": str(e), "traceback": traceback.format_exc() }

def process_document_convertion(input_path, options, meta, current_task):
    output_path = os.path.join(app.config["MEDIA_PATH"], current_task.id)
    if (meta["mimetype"] == "application/pdf"):
        script = app.config["GHOSTSCRIPT_EXEC"]
        if options.get("output_pdf_version", None) != "1":
            script[1] = script[1] + "=" + options.get("output_pdf_version", None)
        run(script + ['-sOutputFile=' + output_path, input_path])

        temp_path = input_path if not check_file_content(input_path, output_path) else output_path

        force_ocr = 0
        while has_PDFA_XMP(temp_path) == False:
            if (force_ocr == 0):
                script = app.config["OCRMYPDF"]["EXEC"] + [app.config["OCRMYPDF"]["OUT"] + "-" + options.get("output_pdf_version", None)]
            elif (force_ocr > 1):
                raise Exception('It was not possible to convert file ' + meta["filename"] + ' to PDF/A.')
            run(script + [app.config["OCRMYPDF"]["FORCE"][force_ocr], temp_path, output_path])
            temp_path= output_path
            force_ocr += 1
    else:
        if options["format"] in app.config[app.config["CONVERTABLE_MIMETYPES"][meta["mimetype"]]["formats"]]:
            filter = ''
            if (options["format"] == "pdf"):
                pdf_export_param = app.config["PDF_EXPORT_PARAMS"]
                pdf_export_param["SelectPdfVersion"]["value"] = options["output_pdf_version"]
                filter = ':' + options["filter"] + ':' + json.dumps(pdf_export_param)
            soffice = run(['soffice', '--headless', '--infilter=' + app.config["CONVERTABLE_MIMETYPES"][meta["mimetype"]]["filter"], '--convert-to', options["format"] + filter, '--outdir', app.config["MEDIA_PATH"], input_path])
            if soffice.returncode != 0:
                raise Exception(soffice.stderr)
            os.rename(os.path.splitext(input_path)[0] + '.' + options["format"], output_path)
        else:
            raise Exception("File can't be in converted to format provided")

    output_filetype = app.config["OUTPUT_FILETYPE_" + options["format"].upper()]
    mimetype = output_filetype["mimetype"]
    filetype = output_filetype["name"]

    if filetype == "PDF/A":
        remove_XMPMeta(output_path) #Removes XMP Metadata

        if app.config["THUMBNAILS_GENERATE"] and options.get("thumbnails", None): # generate thumbnails
            output_path, file_name = thumbnail_generator(input_path, options, meta, current_task, None)

    file_name = "{0}.{1}".format(meta["filename"], options["format"])
    fileSize = os.path.getsize(output_path)
    remove_file(input_path)
    return { "fileName": file_name, "mimeType": mimetype, "fileType": filetype, "fileSize": fileSize, "has_failed": False }

def process_image_convertion(input_path, options, meta, current_task):
    removeAlpha(input_path)
    correct_orientation(input_path)

    with NamedTemporaryFile(dir=app.config["MEDIA_PATH"], delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(imagesToPdf(input_path))
        tmp_file.flush()
    remove_file(input_path)
    meta["mimetype"] = "application/pdf"
    return process_document_convertion(tmp_file.name, options, meta, current_task)

def thumbnail_generator(input_path, options, meta, current_task, original_document):
    with TemporaryDirectory() as tmp_dir:  # create temp dir where output'll be stored
        is_created = False
        if meta["mimetype"] == "application/pdf":
            pdf_path = input_path
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
