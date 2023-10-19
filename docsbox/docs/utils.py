import os
import zipfile
import ujson
import itertools
import magic
import re
import piexif
import exiftool
from piexif import InvalidImageDataError

from requests import exceptions
from xml.parsers.expat import ExpatError
from PyPDF2 import PdfReader
from PyPDF2.errors import PyPdfError
from libxmp import XMPFiles, consts
from wand.image import Image
from PIL import Image as PIL_Image, ExifTags
from pillow_heif import register_heif_opener
from tempfile import NamedTemporaryFile
from docsbox import app, is_worker
from docsbox.docs.via_controller import *

if is_worker:
    register_heif_opener()


def make_zip_archive(uuid, tmp_dir):
    """
    Creates ZIP archive from given @tmp_dir.
    """
    zipname = "{0}.zip".format(uuid)
    result_path = os.path.join(app.config["MEDIA_PATH"], zipname)

    with zipfile.ZipFile(result_path, "w") as output:
        for dirname, subdirs, files in os.walk(tmp_dir):
            for filename in files:
                path = os.path.join(dirname, filename)
                output.write(path, path.split(tmp_dir)[1])
    return result_path, zipname


def set_options(headers, mimetype):
    """
    Validates options
    """
    if mimetype in app.config["CONVERTABLE_MIMETYPES"]:
        options = app.config[app.config["CONVERTABLE_MIMETYPES"][mimetype]["default_options"]]
    else:
        options = app.config["PDF_DEFAULT_OPTIONS"]
    if headers:
        if 'conversion-format' in headers:
            conversion_format = headers["conversion-format"]
            if mimetype in app.config["CONVERTABLE_MIMETYPES"] and conversion_format in app.config[app.config["CONVERTABLE_MIMETYPES"][mimetype]["formats"]]:
                options["format"] = conversion_format
            else:
                message = "'{0}' mimetype can't be converted to '{1}'"
                raise ValueError(message.format(mimetype, conversion_format))    
        
        if 'output-pdf-version' in headers:
            output_pdf_version = headers["output-pdf-version"]
            if output_pdf_version in ["1", "2"]:
                options["output_pdf_version"] = output_pdf_version
            else:
                raise ValueError("Invalid 'output_pdf_version' value")

        if 'Via-Allowed-Users' in headers:
            options["via_allowed_users"] = headers['Via-Allowed-Users']
        else:
            options["via_allowed_users"] = app.config["VIA_ALLOWED_USERS"]

        if 'thumbnails' in headers:
            # check for thumbnails options on request and if they are valid
            thumbnails = ujson.loads(headers["thumbnails"])
            # THUMBNAILS_GENERATE is configured as False
            if app.config["THUMBNAILS_GENERATE"] and thumbnails:
                if not isinstance(thumbnails, dict):
                    raise ValueError("Invalid 'thumbnails' value")
                else:
                    thumbnails_size = thumbnails.get("size", None)
                    if not isinstance(thumbnails_size, str) or not thumbnails_size:
                        raise ValueError("Invalid 'size' value")
                    else:
                        try:
                            (width, height) = map(
                                int, thumbnails_size.split("x"))
                        except ValueError:
                            raise ValueError("Invalid 'size' value")
                        else:
                            options["thumbnails"]["size"] = (width, height)
    return options


def make_thumbnails(image, tmp_dir, size):
    """ 
    This method is not called while THUMBNAILS_GENERATE in settings.py is false
    """
    thumbnails_folder = os.path.join(tmp_dir, "thumbnails/")
    os.mkdir(thumbnails_folder)
    (width, height) = size
    for index, page in enumerate(image.sequence):
        with Image(page) as page:
            filename = os.path.join(thumbnails_folder, "{0}.png".format(index))
            page.resize(width, height)
            if app.config["THUMBNAILS_QUANTIZE"]:
                page.quantize(app.config["THUMBNAILS_QUANTIZE_COLORS"],
                              app.config["THUMBNAILS_QUANTIZE_COLORSPACE"], 0, True, True)
            page.save(filename=filename)
    else:
        image.close()


def get_pdfa_version(nodes):
    part, conformance = "", ""
    for x in nodes:
        if x.nodeName == "pdfaid:part":
            part =  x.firstChild.nodeValue
        if x.nodeName == "pdfaid:conformance":
            conformance = x.firstChild.nodeValue
    return part + conformance


def store_file_from_id(file_id, filename):
    try:
        via_response = get_file_from_via(file_id)
        if via_response.status_code == 200:
            return store_file(via_response, filename, True)
        elif via_response.status_code == 404:
            raise VIAException(404, "File id was not found.")
        else:
            raise VIAException(via_response.status_code, via_response)
    except exceptions.Timeout:
        raise VIAException(504, "VIA service took too long to respond.")


def store_file(data, filename, stream=False):
    suffix = os.path.splitext(filename)[1] if filename else ""
    with NamedTemporaryFile(delete=False, dir=app.config["MEDIA_PATH"], suffix=suffix) as tmp_file:
        if stream:
            for chunk in data.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
        else:
            data.save(tmp_file)
    return tmp_file.name


def get_file_mimetype_from_id(file_id, filename=None):
    try:
        via_response = get_file_from_via(file_id)
        if via_response.status_code == 200:
            mimetype = via_response.headers.get('Content-Type')
            if mimetype is None or mimetype == "application/pdf" or mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
                mimetype = get_file_mimetype_from_data(via_response, filename, stream=True)
            return mimetype
        elif via_response.status_code == 404:
            raise VIAException(404, "File id was not found.")
        else:
            raise VIAException(via_response.status_code, via_response)
    except exceptions.Timeout:
        raise VIAException(504, "VIA service took too long to respond.")


def get_file_mimetype_from_data(data, filename, stream=False):
    suffix = os.path.splitext(filename)[1] if filename else ""
    with NamedTemporaryFile(suffix=suffix) as tmp_file:
        if stream:
            for chunk in data.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
        else:
            data.save(tmp_file)
        tmp_file.flush()
        mimetype = get_file_mimetype(tmp_file.name)
    return mimetype


def get_file_mimetype(file):
    try:
        mime_type_file = exiftool.ExifToolHelper().get_metadata(file)[0]["File:MIMEType"]
        if mime_type_file == "application/pdf":
            # Check is PDF/A and Version
            with open(file, mode="rb") as file_data:
                input = PdfReader(file_data, strict=False)
                try:
                    metadata = input.xmp_metadata
                    if metadata:
                        pdfa = app.config["PDFA"]
                        nodes = metadata.get_nodes_in_namespace("", pdfa["NAMESPACE"])
                        if get_pdfa_version(nodes) in pdfa["ACCEPTED_VERSIONS"]:
                            mime_type_file = "application/pdfa"
                except ExpatError:
                    app.logger.log(logging.WARNING, "File {0} has not well-formed XMP data, could not verify if application/pdf has PDF/A1 DOCINFO.".format(file))

        elif mime_type_file in app.config["GENERIC_MIMETYPES"]:
            mime_type_file = magic.from_file(file, mime=True)
            if mime_type_file in app.config["GENERIC_MIMETYPES"]:
                with open(file, mode="rb") as file_data:
                    document_type_file = magic.from_buffer(file_data.read(2048))
                    for file_mimetype, file_format in itertools.zip_longest(
                            app.config["FILEMIMETYPES"],
                            app.config["FILEFORMATS"]):
                        if document_type_file in file_format:
                            mime_type_file = file_mimetype
    except (ValueError, PyPdfError):
        mime_type_file = "Unknown/Corrupted"
    return mime_type_file


def remove_extension(file):
    return os.path.splitext(file)[0]


def is_valid_uuid(uuid):
    return bool(re.match(r"([0-f]{8}-[0-f]{4}-[0-f]{4}-[0-f]{4}-[0-f]{12})", uuid))


def remove_xmp_meta(file):
    xmpfile = XMPFiles(file_path=file, open_forupdate=True)
    xmp = xmpfile.get_xmp()
    if xmp:
        xmp.set_property(consts.XMP_NS_PDF, 'pdf:Producer', 'Document Converter')
        xmp.set_property(consts.XMP_NS_XMP, 'xmp:CreatorTool', 'Document Converter')
        xmp.set_property(consts.XMP_NS_XMP_MM , 'xmpMM:DocumentID', '')

        xmp.delete_property(consts.XMP_NS_DC, 'dc:format')
        xmp.delete_property(consts.XMP_NS_DC, 'dc:creator')
        xmp.delete_property(consts.XMP_NS_DC, 'dc:description')
    try:
        xmpfile.put_xmp(xmp)
    except:
        xmpfile.close_file()
        return
    xmpfile.close_file()


def has_pdfa_xmp(file):
    try:
        with open(file, mode="rb") as fileData:
            reader = PdfReader(fileData, strict=False)
            metadata = reader.xmp_metadata
            if metadata is not None:
                pdfa = app.config["PDFA"]
                nodes = metadata.get_nodes_in_namespace("", pdfa["NAMESPACE"])
                if get_pdfa_version(nodes) in pdfa["ACCEPTED_VERSIONS"]:
                    return True
            return False
    except Exception as e:
        app.logger.log(logging.ERROR, str(e))
        return False


def remove_alpha(image_path):
    with PIL_Image.open(image_path) as image:
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            alpha = image.convert('RGBA').getchannel('A')
            bg = PIL_Image.new("RGB", image.size, (255, 255, 255, 255))
            bg.paste(image, mask=alpha)
            bg.convert('RGB')
            bg.save(image_path, image.format)


def correct_orientation(image_path):
    try:
        with PIL_Image.open(image_path) as image:
            if hasattr(image, '__getexif'):
                exif = image._getexif()
                if exif:
                    exif_dict = piexif.load(image_path)
                    del exif_dict["1st"]
                    del exif_dict["thumbnail"]
                    for tag, value in exif.items():
                        if ExifTags.TAGS.get(tag, tag) == "Orientation":
                            if value == 0:
                                exif_dict["0th"][piexif.ImageIFD.Orientation] = 1
                            elif value in (2, 4):
                                exif_dict["0th"][piexif.ImageIFD.Orientation] = value - 1
                            elif value in (5, 7):
                                exif_dict["0th"][piexif.ImageIFD.Orientation] = value + 1
                    exif_dict['Exif'][41729] = b'1'  # workaround to avoid type error
                    exif_bytes = piexif.dump(exif_dict)
                    image.save(image_path, image.format, exif=exif_bytes)
    except InvalidImageDataError:
        # Image format is not supported, ignore the error and move on
        pass


def check_file_content(original, converted):
    original_page_num = 0
    converted_page_num = 0
    has_content = False
    with open(original, mode="rb") as original_data:
        original_reader = PdfReader(original_data, strict=False)
        original_page_num = len(original_reader.pages)

    with open(converted, mode="rb") as converted_data:
        converted_reader = PdfReader(converted_data, strict=False)
        has_content = converted_reader.pages[0].get_contents()
        converted_page_num = len(converted_reader.pages)

    return has_content and original_page_num != 0 and converted_page_num != 0 and original_page_num == converted_page_num


def heic_to_png(path):
    tmp_file = app.config["MEDIA_PATH"] + "tmp"
    with PIL_Image.open(path) as image:
        image.save(tmp_file, "png")
    return tmp_file


def check_file_path(path):
    return os.path.exists(path)
