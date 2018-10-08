import os
import zipfile
import ujson

from wand.image import Image

from magic import Magic

from flask import current_app as app


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
                supported = (fmt in app.config["CONVERTABLE_MIMETYPES"][mimetype]["formats"])
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
        options = app.config["DEFAULT_OPTIONS"]
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


def get_file_mimetype(file):
    with Magic() as magic:  # detect mimetype
        return magic.from_file(file.name)

