import os
import zipfile

from docsbox.docs.classes.attachment import Attachment
import pikepdf
import ujson
import itertools
import magic
import re
import piexif
import exiftool
from piexif import InvalidImageDataError

from requests import exceptions
from xml.parsers.expat import ExpatError
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from libxmp import XMPFiles, consts
from wand.image import Image
from PIL import Image as PIL_Image
from pillow_heif import register_heif_opener
from tempfile import NamedTemporaryFile
from docsbox import is_worker
from docsbox.docs.via_controller import *

if is_worker:
    register_heif_opener()


def make_zip_archive(uuid: str, tmp_dir: str):
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


def set_options(headers: dict, mimetype:str) -> dict:
    """
    Validates options
    """
    if mimetype in app.config["CONVERTABLE_MIMETYPES"]:
        options = app.config[app.config["CONVERTABLE_MIMETYPES"][mimetype]["default_options"]]
    else:
        options = app.config["PDF_DEFAULT_OPTIONS"]
    if headers:
        # Lower case keys for header names
        headers = {k.lower(): v for k, v in headers.items()}

        if 'conversion-format' in headers:
            conversion_format = headers["conversion-format"]
            if mimetype in app.config["CONVERTABLE_MIMETYPES"] and conversion_format in app.config[app.config["CONVERTABLE_MIMETYPES"][mimetype]["formats"]]:
                options["format"] = conversion_format
            else:
                message = "'{0}' mimetype can't be converted to '{1}'"
                raise ValueError(message.format(mimetype, conversion_format))    

        if 'output-pdf-version' in headers:
            output_pdf_version = headers["output-pdf-version"]
            if output_pdf_version in ["1", "2", "3"]:
                options["output_pdf_version"] = output_pdf_version
            else:
                raise ValueError("Invalid 'output_pdf_version' value. Allowed are 1, 2 and 3")

        if 'via-allowed-users' in headers:
            options["via_allowed_users"] = headers['via-allowed-users']
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


def make_thumbnails(image, tmp_dir: str, size):
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
            part = x.firstChild.nodeValue
        if x.nodeName == "pdfaid:conformance":
            conformance = x.firstChild.nodeValue
    return part + conformance


def store_file_from_id(file_id: str, filename: str):
    try:
        via_response = get_file_from_via(file_id)
        if via_response.status_code == 200:
            mimetype = via_response.headers.get('Content-Type')
            return store_file(via_response, filename, True), mimetype
        elif via_response.status_code == 404:
            raise VIAException(404, "File id was not found.")
        else:
            raise VIAException(via_response.status_code, via_response)
    except exceptions.Timeout:
        raise VIAException(504, "VIA service took too long to respond.")


def store_file(data, filename: str, stream=False):
    suffix = os.path.splitext(filename)[1] if filename else ""
    with NamedTemporaryFile(delete=False, dir=app.config["MEDIA_PATH"], suffix=suffix) as tmp_file:
        if stream:
            for chunk in data.iter_content(chunk_size=8192):
                tmp_file.write(chunk)
        else:
            data.save(tmp_file)
    return tmp_file.name


def get_file_mimetype_from_data(data, filename: str, stream=False):
    suffix = os.path.splitext(filename)[1] if filename else ""
    with NamedTemporaryFile(suffix=suffix) as tmp_file:
        if stream:
            if hasattr(data, "iter_content"):
                for chunk in data.iter_content(chunk_size=8192):
                    tmp_file.write(chunk)
            elif hasattr(data, "read"):
                for chunk in iter(lambda: data.read(8192), b""):
                    tmp_file.write(chunk)
            else:
                tmp_file.write(data)
        else:
            if isinstance(data, (bytes, bytearray)):
                tmp_file.write(data)
            elif hasattr(data, "save"):
                data.save(tmp_file)
            elif hasattr(data, "read"):
                for chunk in iter(lambda: data.read(8192), b""):
                    tmp_file.write(chunk)
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        mimetype, version = get_file_mimetype(tmp_file.name)
    return mimetype, version


def get_file_mimetype(file: str, req_mimetype: str = None):
    if req_mimetype is None or req_mimetype == "application/pdf" or req_mimetype not in app.config["CONVERTABLE_MIMETYPES"]:
        mime_type_file: str = ""
        try:
            mime_type_file = exiftool.ExifToolHelper().get_metadata(file)[0]["File:MIMEType"]
        except Exception:
            app.logger.log(logging.WARNING, f"Error checking mimetype using ExifTool, falling back to libmagic", exc_info=True)
            pass

        if not mime_type_file or mime_type_file in app.config["GENERIC_MIMETYPES"]:
            try:
                mime_type_file = magic.from_file(file, mime=True)
            except Exception:
                app.logger.log(logging.WARNING, f"Error checking mimetype using libmagic, falling back to signature table", exc_info=True)
                pass

        if not mime_type_file or mime_type_file in app.config["GENERIC_MIMETYPES"]:
            try:
                with open(file, mode="rb") as file_data:
                    document_type_file: str = magic.from_buffer(file_data.read(2048))
                    for file_mimetype, file_format in itertools.zip_longest(
                            app.config["FILEMIMETYPES"],
                            app.config["FILEFORMATS"]):
                        if document_type_file in file_format:
                            mime_type_file = file_mimetype
            except Exception:
                app.logger.exception(f"Error checking mimetype using signature table")
                pass

        if not mime_type_file:
            mime_type_file = "Unknown/Corrupted"

        if mime_type_file == "application/pdf":
            protection_status = pdf_protection_status(file)
            if protection_status:
                mime_type_file = protection_status
                return mime_type_file, ""
            return mime_type_file, read_pdf_version(file)
    else:
        mime_type_file = req_mimetype

    return mime_type_file, ""


def read_pdf_version(file: str):
    version = ""
    with open(file, mode="rb") as file_data:
        pdf = PdfReader(file_data, strict=False)
        try:
            metadata = pdf.xmp_metadata
            if metadata:
                pdfa_config = app.config["PDFA"]
                nodes = metadata.get_nodes_in_namespace("", pdfa_config["NAMESPACE"])
                version = get_pdfa_version(nodes)
        except ExpatError:
            app.logger.log(
                logging.WARNING,
                "File {0} has not well-formed XMP data, could not verify if application/pdf has PDF/A DOCINFO.".format(file))

    return version


def pdf_protection_status(path: str):
    try:
        reader = PdfReader(path, strict=False)
    except (PdfReadError, OSError):
        return None

    if reader.is_encrypted:
        # Try the owner-password shortcut – empty string.
        # decrypt() returns:
        #   1 → user password accepted
        #   2 → owner password accepted
        #   0 → password wrong
        if reader.decrypt("") in (1, 2):
            return "password-protected-partial"
        return "password-protected"
    return None


def remove_extension(file: str):
    return os.path.splitext(file)[0]


def is_valid_uuid(uuid: str):
    return bool(re.match(r"([0-f]{8}-[0-f]{4}-[0-f]{4}-[0-f]{4}-[0-f]{12})", uuid))


def remove_xmp_meta(file: str, task_id: str):
    xmpfile = XMPFiles(file_path=file, open_forupdate=True)
    xmp = xmpfile.get_xmp()
    if xmp:
        xmp.set_property(consts.XMP_NS_PDF, 'pdf:Producer', 'Oikeusministeriö, asiakirjojen konversiopalvelu')
        xmp.set_property(consts.XMP_NS_XMP, 'xmp:CreatorTool', 'DCS')
        xmp.set_property(consts.XMP_NS_XMP_MM, 'xmpMM:DocumentID', task_id)

        xmp.delete_property(consts.XMP_NS_DC, 'dc:format')
        xmp.delete_property(consts.XMP_NS_DC, 'dc:creator')
        xmp.delete_property(consts.XMP_NS_DC, 'dc:description')
    try:
        xmpfile.put_xmp(xmp)
    except:
        pass
    finally:
        xmpfile.close_file()


def has_pdfa_xmp(file: str):
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
        app.logger.log(logging.ERROR, repr(e))
        return False


def remove_alpha(image_path):
    with PIL_Image.open(image_path) as image:
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            alpha = image.convert('RGBA').getchannel('A')
            bg = PIL_Image.new("RGB", image.size, (255, 255, 255, 255))
            bg.paste(image, mask=alpha)
            bg.convert('RGB')
            bg.save(image_path, image.format)


def sanitize_metadata(image_path: str):
    try:
        with PIL_Image.open(image_path) as image:
            if hasattr(image, 'getexif'):
                exif = image.getexif()
                if exif:
                    # Exif data is not supported in Piexif for other formats than jpeg and tiff
                    # if the format is not jpeg or tiff, clear exif data
                    # PNG support might be coming sometime: https://github.com/hMatoba/Piexif/issues/49
                    if image.format not in ("JPEG", "TIFF"):
                        image.save(image_path, image.format)
                        return

                    exif_dict = piexif.load(image_path)

                    # Remove unneeded metadata to save bytes
                    del exif_dict["1st"]
                    del exif_dict["thumbnail"]

                    for ifd_name in exif_dict.keys():
                        for tag in dict(exif_dict[ifd_name]):
                            tag_info = piexif.TAGS[ifd_name].get(tag)
                            value = exif_dict[ifd_name][tag]

                            # Check that all integer values are within signed 32bit
                            # since piexif requires them to be signed and some image files
                            # might contain unsigned values for signed types
                            if tag_info:
                                tag_type = tag_info['type']
                                if tag_type == piexif.TYPES.SRational:
                                    if isinstance(value, tuple) and len(value) == 2:
                                        exif_dict[ifd_name][tag] = tuple(unsigned_to_signed(n, 32) for n in value)
                                elif tag_type == piexif.TYPES.SLong:
                                    if isinstance(value, int):
                                        exif_dict[ifd_name][tag] = unsigned_to_signed(value, 32)
                                elif tag_type == piexif.TYPES.SShort:
                                    if isinstance(value, int):
                                        exif_dict[ifd_name][tag] = unsigned_to_signed(value, 16)
                                elif tag_type == piexif.TYPES.SByte:
                                    if isinstance(value, int):
                                        exif_dict[ifd_name][tag] = unsigned_to_signed(value, 8)

                            # Correct orientation for mirrored images since img2pdf does not support
                            # mirrored images, so we will change the orientation for these to be not
                            # mirrored instead of failin the conversion. We could also modify the image by
                            # using another library for the mirrored ones to maintain their integrity.
                            # With this implementation, they will be mirrored in a non-natural way
                            # https://www.daveperrett.com/articles/2012/07/28/exif-orientation-handling-is-a-ghetto/
                            # https://github.com/recurser/exif-orientation-examples
                            if tag == piexif.ImageIFD.Orientation:
                                if value == 0:
                                    exif_dict[ifd_name][tag] = 1
                                elif value in (2, 4):
                                    exif_dict[ifd_name][tag] = value - 1
                                elif value in (5, 7):
                                    exif_dict[ifd_name][tag] = value + 1

                    # https://github.com/hMatoba/Piexif/issues/95
                    if piexif.ExifIFD.SceneType in exif_dict['Exif'] and isinstance(exif_dict['Exif'][piexif.ExifIFD.SceneType], int):
                        exif_dict['Exif'][piexif.ExifIFD.SceneType] = str(exif_dict['Exif'][piexif.ExifIFD.SceneType]).encode('utf-8')

                    try:
                        exif_bytes = piexif.dump(exif_dict)
                        image.save(image_path, image.format, exif=exif_bytes)
                    except Exception as e:
                        # Do not fail the conversion if we fail here
                        app.logger.log(logging.ERROR, repr(e))
                        pass
    except InvalidImageDataError as e:
        app.logger.log(logging.ERROR, repr(e))
        # Image format is not supported, ignore the error and move on
        pass


def unsigned_to_signed(value, bit_count):
    MAX_INT = 2**(bit_count - 1) - 1
    if value > MAX_INT:
        return value - 2**bit_count
    else:
        return value


def check_file_content(original: str, converted: str):
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


def heic_to_png(path: str):
    tmp_file: str = app.config["MEDIA_PATH"] + "tmp"
    with PIL_Image.open(path) as image:
        image.save(tmp_file, "png")
    return tmp_file


def check_file_path(path: str):
    return os.path.exists(path)


def fill_cmd_param(cmd: list[str], param: str, value: str):
    """
    Fills parameters in a string, parameters are defined with a $ prefix

    :param cmd: The command with parts separated in an array
    :param param: The parameter to replace, without the $ prefic
    :param value: The value to replace the param with
    """
    param_with_marker = f"${param}"
    try:
        pos = cmd.index(next(filter(lambda x: param_with_marker in x, cmd), None))
        if pos is not None:
            cmd[pos] = cmd[pos].replace(param_with_marker, value)
    except ValueError:
        # No param found, do not replace anything
        pass

    return cmd


def extract_pdf_attachments(pdf_path: str, output_pdf_version: str):
    """
    Extracts all attachments in the pdf file found in the path and returns them
    """
    if output_pdf_version == "1":
        # PDF/A-1 does not support attachments
        return

    attachments = dict()
    with pikepdf.open(pdf_path) as pdf:

        for name, filespec in pdf.attachments.items():
            file_bytes = filespec.get_file().read_bytes()

            f_props = dict(filespec.get_file().obj.items())

            meta_dict = dict(filespec.obj)
            meta_dict.pop('/EF', None)

            attachments[name] = Attachment(file_bytes, f_props, meta_dict)

    return attachments


def attach_pdf_attachments(pdf_path: str, attachments: dict[str, Attachment], output_pdf_version: str):
    """
    Attaches the attachments to the pdf file, if the output PDF version supports them
    """
    if output_pdf_version == "1":
        # PDF/A-1 does not support attachments
        return

    if not attachments:
        return

    with pikepdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        edited = False
        for name, attachment in attachments.items():
            file_mimetype, _ = get_file_mimetype_from_data(attachment.bytes, name, False)
            if output_pdf_version == "2" and file_mimetype != "application/pdf":
                continue

            # Create the filespec for the file, add the supported args right away
            filespec = pikepdf.AttachedFileSpec(
                pdf,
                attachment.bytes,
                filename=name,
                mime_type=file_mimetype,
                description=_pdfstr_to_str(attachment.file_spec.get('/Desc', '')),
                creation_date=_pdfstr_to_str(attachment.file_spec.get('/CreationDate', '')),
                mod_date=_pdfstr_to_str(attachment.file_spec.get('/ModDate', '')),
            )
            pdf.attachments[name] = filespec

            # Add the rest of the file metadata which were not supported by the constructor
            extra = {k: v for k, v in attachment.file_spec.items()
                     if k not in {'/Desc', '/CreationDate', '/ModDate', '/AFRelationship'}}

            if '/AFRelationship' in attachment.file_spec:
                extra['/AFRelationship'] = pikepdf.Name(attachment.file_spec['/AFRelationship'].lstrip('/'))

            for k, v in extra.items():
                filespec.obj[k] = v

            edited = True

        if edited:
            pdf.save(pdf_path)


def _pdfstr_to_str(value):
    """Return *value* as a plain Python str."""
    if isinstance(value, str):
        return value
    if value is None:
        return ''
    return str(value)
