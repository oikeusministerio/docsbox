import os
import json
from docsbox import app, db
from docsbox.docs.tasks import FileInfo
from docsbox.docs.utils import check_file_path
from datetime import datetime, timedelta


def cleaning_job():
    file_ttl = datetime.now() - timedelta(seconds=app.config["FILE_TTL"])
    keys = db.keys('fileId:*')

    print("Starting file cleaning scheduled job.")

    keys_to_remove=[]
    for key in keys :
        file_info: FileInfo = json.loads(db.get(key))
        if datetime.strptime(file_info.datetime, '%Y/%m/%d-%H:%M:%S') < file_ttl:
            if file_info.file_path and check_file_path(file_info.file_path):
                os.remove(file_info.file_path)
            keys_to_remove.append(key)

    if keys_to_remove:
        db.delete(*keys_to_remove)
    print("Removed %d entries." % keys_to_remove.__len__())

    if not db.keys('fileId:*'):
        media_file_list = os.listdir(app.config["MEDIA_PATH"])
        print("%d files in media directory for deletion" % media_file_list.__len__())
        if media_file_list:
            for file in media_file_list:
                file_path = os.path.join(app.config["MEDIA_PATH"], file)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print('Failed to delete %s. Reason: %s' % (file_path, e))
