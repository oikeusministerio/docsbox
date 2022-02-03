import os
import zipfile
import ujson
import itertools
import magic
import re
import piexif
import logging
import exiftool

from xml.parsers.expat import ExpatError
from PyPDF3 import PdfFileReader
from PyPDF3.pdf import PageObject
from PyPDF3.utils import PdfReadError
from libxmp import XMPFiles, consts
from wand.image import Image
from PIL import Image as PIL_Image, ExifTags
from docsbox import app


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
    options = app.config[app.config["CONVERTABLE_MIMETYPES"][mimetype]["default_options"]]
    if headers:
        if 'conversion-format' in headers:
            conversion_format = headers["conversion-format"]
            if conversion_format in app.config[app.config["CONVERTABLE_MIMETYPES"][mimetype]["formats"]]:
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
    return index

def get_pdfa_version(nodes):
    part, conformance = "", ""
    for x in nodes:
        if x.nodeName == "pdfaid:part":
            part =  x.firstChild.nodeValue
        if x.nodeName == "pdfaid:conformance":
            conformance = x.firstChild.nodeValue
    return part + conformance

def get_file_mimetype(file, format):
    try:   
        mimeTypeFile = exiftool.ExifToolHelper().get_metadata(file.name)[0]["File:MIMEType"]
        if mimeTypeFile == "application/pdf":
            with open(file.name, mode="rb") as fileData:
                input = PdfFileReader(fileData, strict=False)
                try:
                    metadata = input.getXmpMetadata()
                    if metadata:
                        pdfa=app.config["PDFA"]
                        nodes = metadata.getNodesInNamespace("", pdfa["NAMESPACE"])
                        if get_pdfa_version(nodes) in pdfa["ACCEPTED_VERSIONS"]:
                            mimeTypeFile = "application/pdfa"
                except (ExpatError):
                    app.logger.log(logging.WARNING, "File {0} has not well-formed XMP data, could not verify if application/pdf has PDF/A1 DOCINFO.".format(file.name))
        elif mimeTypeFile == "application/zip" or mimeTypeFile == "text/plain":
            mimeTypeFile = magic.from_file(file.name, mime=True)
            if mimeTypeFile == "application/octet-stream":
                with open(file.name, mode="rb") as fileData:
                    documentTypeFile = magic.from_buffer(fileData.read(2048))
                    for (fileMimetype, fileFormat) in itertools.zip_longest(app.config["FILEMIMETYPES"], app.config["FILEFORMATS"]): 
                        if documentTypeFile in fileFormat:
                            mimeTypeFile = fileMimetype
    except (ValueError, PdfReadError):
        mimeTypeFile = "Unknown/Corrupted"
    return mimeTypeFile

def remove_extension(file):
    return os.path.splitext(file)[0]

def is_valid_uuid(uuid):
    return bool(re.match(r"([0-f]{8}-[0-f]{4}-[0-f]{4}-[0-f]{4}-[0-f]{12})", uuid))

def remove_XMPMeta(file):

    xmpfile = XMPFiles(file_path=file, open_forupdate=True)
    xmp = xmpfile.get_xmp()
    xmp.set_property(consts.XMP_NS_PDF, 'pdf:Producer', 'Document Converter')
    xmp.set_property(consts.XMP_NS_XMP, 'xmp:CreatorTool', 'Document Converter')
    xmp.set_property(consts.XMP_NS_XMP_MM , 'xmpMM:DocumentID', '')

    xmp.delete_property(consts.XMP_NS_DC, 'dc:format')
    xmp.delete_property(consts.XMP_NS_DC, 'dc:title')
    xmp.delete_property(consts.XMP_NS_DC, 'dc:creator')
    xmp.delete_property(consts.XMP_NS_DC, 'dc:description')
    try:
        xmpfile.put_xmp(xmp)
    except:
        xmpfile.close_file()
        return
    xmpfile.close_file()

def has_PDFA_XMP(file):
    try:
        with open(file, mode="rb") as fileData:
            xmpfile = PdfFileReader(fileData, strict=False)
            metadata = xmpfile.getXmpMetadata()
            if metadata is not None:
                pdfa=app.config["PDFA"]
                nodes = metadata.getNodesInNamespace("", pdfa["NAMESPACE"])
                if get_pdfa_version(nodes) in pdfa["ACCEPTED_VERSIONS"]:
                    return True
            return False
    except:
        return False

def removeAlpha(image_path):
    with PIL_Image.open(image_path) as image:
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            alpha = image.convert('RGBA').getchannel('A')
            bg = PIL_Image.new("RGB", image.size, (255,255,255,255))
            bg.paste(image, mask=alpha)
            bg.convert('RGB')
            bg.save(image_path, image.format)

def correct_orientation(image_path):
    with PIL_Image.open(image_path) as image:
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

            exif_bytes = piexif.dump(exif_dict)
            image.save(image_path, image.format, exif=exif_bytes)

def check_file_content(original, converted):
    original_pdf = PdfFileReader(open(original, mode="rb"), strict=False)
    original_page_num = original_pdf.numPages

    with open(converted, mode="rb") as converted_data:
        converted_pdf = PdfFileReader(converted_data, strict=False)
        page = PageObject(converted_data)
        if (page.getContents() is None or original_page_num != converted_pdf.numPages):
            return False
    return True
