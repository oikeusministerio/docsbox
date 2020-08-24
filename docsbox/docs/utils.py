import os
import zipfile
import ujson
import itertools
import magic
import re

from PyPDF2 import PdfFileReader, xmp
from libxmp import XMPFiles, consts
from wand.image import Image
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

def set_options(options, mimetype):
    """
    Validates options
    """
    if options:  # options validation
        options = ujson.loads(options)
        formats = options.get("formats", None)
        if not isinstance(formats, list) or not formats:
            raise ValueError("Invalid 'formats' value")
        else:
            for fmt in formats:
                supported = (fmt in app.config[app.config["CONVERTABLE_MIMETYPES"][mimetype]["formats"]])
                if not supported:
                    message = "'{0}' mimetype can't be converted to '{1}'"
                    raise ValueError(message.format(mimetype, fmt))
        thumbnails = options.get("thumbnails", None) # check for thumbnails options on request and if they are valid
        if app.config["THUMBNAILS_GENERATE"] and thumbnails: # THUMBNAILS_GENERATE is configured as False
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
    else:
        options = app.config[app.config["CONVERTABLE_MIMETYPES"][mimetype]["default_options"]]
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

def get_file_mimetype(file):
    with open(file.name, mode="rb") as fileData:
        try:
            mimeTypeFile = magic.Magic(flags=magic.MAGIC_MIME_TYPE).id_filename(file.name)
            documentTypeFile = magic.Magic().id_buffer(fileData.read(1024))

            if mimeTypeFile == "application/pdf":
                    input = PdfFileReader(fileData)
                    metadata = input.getXmpMetadata()
                    if metadata is not None:
                        pdfa=app.config["PDFA"]
                        nodes = metadata.getNodesInNamespace("", pdfa["NAMESPACE"]) 
                        if get_pdfa_version(nodes) in pdfa["ACCEPTED_VERSIONS"]:
                            mimeTypeFile = "application/pdfa"
            else:
                for (fileMimetype, fileFormat) in itertools.zip_longest(app.config["FILEMIMETYPES"], app.config["FILEFORMATS"]): 
                    if (any(x in mimeTypeFile for x in app.config["LIBMAGIC_MIMETYPES"]["content-type"]) and documentTypeFile in fileFormat):
                        mimeTypeFile = fileMimetype
        except ValueError:
            mimeTypeFile = "Unknown/Corrupted"
    return mimeTypeFile

def remove_extension(file):
    return os.path.splitext(file)[0]

def is_valid_uuid(uuid):
    return bool(re.match(r"([0-f]{8}-[0-f]{4}-[0-f]{4}-[0-f]{4}-[0-f]{12})", uuid))

def remove_XMPMeta(file):
    xmpfile = XMPFiles( file_path=file, open_forupdate=True )
    xmp = xmpfile.get_xmp()
    xmp.set_property(consts.XMP_NS_PDF, 'pdf:Producer', 'Document Converter')
    xmp.set_property(consts.XMP_NS_XMP, 'xmp:CreatorTool', 'Document Converter')
    xmp.set_property(consts.XMP_NS_XMP_MM , 'xmpMM:DocumentID', '')

    xmp.delete_property(consts.XMP_NS_DC, 'dc:format')
    xmp.delete_property(consts.XMP_NS_DC, 'dc:title')
    xmp.delete_property(consts.XMP_NS_DC, 'dc:creator')
    xmp.delete_property(consts.XMP_NS_DC, 'dc:description')

    xmpfile.put_xmp(xmp)
    xmpfile.close_file()
