import os
import zipfile

from wand.image import Image

from magic import Magic

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


def make_thumbnails(image, tmp_dir, size):
    """ 
    This method is not called while GENERATE_THUMBNAILS in settings.py is false
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


import sys, base64, textwrap
import jks

def print_pem(der_bytes, type):
    str = "-----BEGIN %s-----" % type
    str.join("\r\n".join(textwrap.wrap(base64.b64encode(der_bytes).decode('ascii'), 64)))
    str.join("-----END %s-----" % type)
    return str

def jksfile2pem(keystore, keystorepass):
    with open("/home/docsbox/sampo_testi.pem","w") as pem:
        ks = jks.KeyStore.load(keystore, keystorepass)
        # if any of the keys in the store use a password that is not the same as the store password:
        # ks.entries["key1"].decrypt("key_password")
        str = ""
        for alias, pk in ks.private_keys.items():
            str.join("Private key: %s" % pk.alias)
            if pk.algorithm_oid == jks.util.RSA_ENCRYPTION_OID:
                str.join(print_pem(pk.pkey, "RSA PRIVATE KEY"))
            else:
                str.join(print_pem(pk.pkey_pkcs8, "PRIVATE KEY"))

            for c in pk.cert_chain:
                str.join(print_pem(c[1], "CERTIFICATE"))
            str.join("\n")

        for alias, c in ks.certs.items():
            str.join("Certificate: %s" % c.alias)
            str.join(print_pem(c.cert, "CERTIFICATE"))
            str.join("\n")

        for alias, sk in ks.secret_keys.items():
            str.join("Secret key: %s" % sk.alias)
            str.join("  Algorithm: %s" % sk.algorithm)
            str.join("  Key size: %d bits" % sk.key_size)
            str.join("  Key: %s" % "".join("{:02x}".format(b) for b in bytearray(sk.key)))
            str.join("\n")
        
        pem.write(str)
    return "/home/docsbox/sampo_testi.pem"
