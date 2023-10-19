import traceback
import json

from subprocess import run
from img2pdf import convert as images_to_pdf
from tempfile import TemporaryDirectory
from rq import get_current_job
from datetime import datetime, timezone
from docsbox import app, rq, db
from docsbox.docs.unoconv import UnoConverter
from docsbox.docs.utils import *
from docsbox.docs.via_controller import *


def get_task(task_id):
    queue = rq.get_queue()
    return queue.fetch_job(task_id)


def remove_file(path):
    """
    Just removes a file.
    Used for deleting original files (uploaded by user) and result files (result of converting)
    """
    return os.remove(path)


@rq.job(timeout=app.config["REDIS_JOB_TIMEOUT"])
def process_convertion_by_id(file_id, headers):
    try:
        if db.exists('fileId:' + file_id) != 0:
            file_info = json.loads(db.get('fileId:' + file_id))
            if "file_path" not in file_info:
                via_response = get_file_from_via(file_id)
                if via_response.status_code == 200:
                    file_info["file_path"] = store_file(via_response, file_info["filename"], stream=True)
                else:
                    return {"has_failed": True, "message": "VIAException code: 404, message: File id was not found.", "traceback": ""}
        else:
            filename = headers.get('Content-Disposition')
            mimetype = headers.get('Content-Type')
            via_response = get_file_from_via(file_id)
            if via_response.status_code == 200:
                file_path = store_file(via_response, filename, stream=True)
                if mimetype is None or mimetype == "application/pdf" or mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                    mimetype = get_file_mimetype(file_path)
            else:
                return {"has_failed": True, "message": "VIAException code: 404, message: File id was not found.", "traceback": ""}
            file_info = {"file_id": file_id, "mimetype": mimetype, "filename": filename, "file_path": file_path, "datetime": datetime.now().strftime('%Y/%m/%d-%H:%M:%S')}
        db.set('fileId:' + file_id, json.dumps(file_info))
        return process_convertion(file_info["file_path"], set_options(headers, file_info["mimetype"]), {"filename": file_info["filename"], "mimetype": file_info["mimetype"], "file_id": file_info["file_id"], "save_in_via": True})
    except Exception as e:
        return {"has_failed": True, "message": str(e), "traceback": traceback.format_exc()}


@rq.job(timeout=app.config["REDIS_JOB_TIMEOUT"])
def process_convertion(path, options, meta):
    if meta["mimetype"] not in app.config["CONVERTABLE_MIMETYPES"]:
        status = "corrupted" if meta["mimetype"] == "Unknown/Corrupted" else "non-convertable"
        message = "Conversion is not possible for filetype " + meta["mimetype"]
        return {"has_failed": True, "status": status, "message": message, "traceback": ""}
    try:
        current_task = get_current_job()
        export_format_type = app.config["CONVERTABLE_MIMETYPES"][meta["mimetype"]]["formats"]
        if export_format_type in app.config["DOCUMENT_CONVERTION_FORMATS"]:
            result = process_document_convertion(path, options, meta, current_task)
        elif export_format_type == "IMAGE_EXPORT_FORMATS":
            result = process_image_convertion(path, options, meta, current_task)
        else:
            return {"has_failed": True, "message": "Conversion for {0} is not supported".format(export_format_type)}
        if meta["save_in_via"] is True:
            r = save_file_on_via(app.config["MEDIA_PATH"] + current_task.id, result["mimeType"], options["via_allowed_users"])
            remove_file(app.config["MEDIA_PATH"] + current_task.id)
            result['fileId'] = r.headers.get("Document-id")
        log_task_completion(current_task, result, meta)
        return result
    except Exception as e:
        return {"has_failed": True, "message": str(e), "traceback": traceback.format_exc()}


def process_document_convertion(input_path, options, meta, current_task):
    output_path = os.path.join(app.config["MEDIA_PATH"], current_task.id)
    if meta["mimetype"] == "application/pdf":
        script = app.config["GHOSTSCRIPT_EXEC"]
        if options.get("output_pdf_version", None) != "1":
            script[1] = script[1] + "=" + options.get("output_pdf_version", None)
        run(script + ['-sOutputFile=' + output_path, input_path])

        temp_path = input_path if not check_file_content(input_path, output_path) else output_path

        force_ocr = 0
        while not has_pdfa_xmp(temp_path):
            if force_ocr == 0:
                script = app.config["OCRMYPDF"]["EXEC"] + [app.config["OCRMYPDF"]["OUT"] + "-" + options.get("output_pdf_version", None)]
            elif force_ocr > 1:
                raise Exception('It was not possible to convert file ' + meta["filename"] + ' to PDF/A.')
            run(script + [app.config["OCRMYPDF"]["FORCE"][force_ocr], temp_path, output_path])
            temp_path = output_path
            force_ocr += 1
    else:
        if options["format"] in app.config[app.config["CONVERTABLE_MIMETYPES"][meta["mimetype"]]["formats"]]:
            UnoConverter().convert(
                inpath=input_path,
                outfilter=options["filter"],
                pdf_version=options["output_pdf_version"],
                outpath=output_path)
        else:
            raise Exception("File can't be in converted to format provided")

    output_filetype = app.config["OUTPUT_FILETYPE_" + options["format"].upper()]
    mimetype = output_filetype["mimetype"]
    filetype = output_filetype["name"]

    if filetype == "PDF/A":
        remove_xmp_meta(output_path)

        if app.config["THUMBNAILS_GENERATE"] and options.get("thumbnails", None):
            output_path, file_name = thumbnail_generator(input_path, options, meta, current_task, None)

    file_name = "{0}.{1}".format(remove_extension(meta["filename"]), options["format"])
    file_size = os.path.getsize(output_path)
    remove_file(input_path)
    return {"fileName": file_name, "mimeType": mimetype, "fileType": filetype, "fileSize": file_size, "has_failed": False}


def process_image_convertion(input_path, options, meta, current_task):
    if meta["mimetype"] == "image/heif":
        tmp_path = heic_to_png(input_path)
        remove_file(input_path)
        input_path = tmp_path

    remove_alpha(input_path)
    correct_orientation(input_path)

    with NamedTemporaryFile(dir=app.config["MEDIA_PATH"], delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(images_to_pdf(input_path))
        tmp_file.flush()
    remove_file(input_path)
    new_metadata = {**meta, "mimetype": "application/pdf"}  # Creates the PDF using Ghostscript instead of LO
    return process_document_convertion(tmp_file.name, options, new_metadata, current_task)


def thumbnail_generator(input_path, options, meta, current_task, original_document):
    with TemporaryDirectory() as tmp_dir:
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
        make_thumbnails(image, tmp_dir, options["thumbnails"]["size"])
        return make_zip_archive(current_task.id, tmp_dir)


def log_task_completion(task, result, meta):
    task_time = datetime.now(timezone.utc) - task.started_at.replace(tzinfo=timezone.utc)
    extra = {
        "task_id": task.id,
        "converted_file_size": str(result["fileSize"]),
        "conversion_time": str(task_time),
        "original_filename": meta["filename"],
        "original_mimetype": meta["mimetype"],
        "converted_filename": result["fileName"],
        "converted_mimetype": result["mimeType"],
    }

    if "file_id" in meta:
        extra["original_file_id"] = meta["file_id"]
    if "fileId" in result:
        extra["converted_file_id"] = result["fileId"]

    app.logger.log(logging.INFO, "Finished conversion task: %s" % task.id, extra=extra)
