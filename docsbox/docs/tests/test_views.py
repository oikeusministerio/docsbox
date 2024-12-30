import os
import unittest
import docsbox
import time
import test_dependencies as dep
from requests import get, post

# Hack to work with Python 3.10
import collections
collections.Callable = collections.abc.Callable


class BaseTestCase(unittest.TestCase):

    via_run = os.getenv("TEST_VIA")

    def setUp(self):
        self.app = docsbox.app
        self.app.config["TESTING"] = True
        self.app.config["CELERY_ALWAYS_EAGER"] = True
        self.inputs = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "inputs/"
        )

    def detection_file_type_via(self, fileId):
        response = post(url="http://nginx:80/conversion-service/get-file-type/" + fileId)
        return response

    def detection_file_type_n_via(self, filename):
        with open(os.path.join(self.inputs, filename), "rb") as data:
            response = post(url="http://nginx:80/conversion-service/get-file-type/0", files={"file": data})
        return response

    def convert_file_via(self, fileId, fileName):
        response = post(url="http://nginx:80/conversion-service/convert/" + fileId, headers={"Content-Disposition": fileName, "Via-Allowed-Users": "test"})
        return response

    def convert_file_n_via(self, filename):
        if filename:
            with open(os.path.join(self.inputs, filename), "rb") as data:
                response = post(url="http://nginx:80/conversion-service/v2/convert/0", files={"file": data})
        else:
            response = post(url="http://nginx:80/conversion-service/v2/convert/0")
        return response

    def convert_file_with_options_via(self, fileId, headers):
        response = post(url="http://nginx:80/conversion-service/convert/" + fileId, headers=headers)
        return response

    def convert_file_with_options_n_via(self, filename, headers):
        with open(os.path.join(self.inputs, filename), "rb") as data:
            response = post(url="http://nginx:80/conversion-service/convert/0", files={"file": data}, headers=headers)
        return response

    def status_file(self, taskId):
        response = get(url="http://nginx:80/conversion-service/status/" + taskId)
        return response

    def download_file(self, taskId):
        response = get(url="http://nginx:80/conversion-service/get-converted-file/" + taskId)
        return response

    def save_file_to_VIA(self, filename, mime_type):
        with open(os.path.join(self.inputs, filename), "rb") as data:
            cert = self.app.config["VIA_CERT_PATH"]
            headers = {"VIA_ALLOWED_USERS": self.app.config["VIA_ALLOWED_USERS"], "Content-type": mime_type}
            response = post(url=self.app.config["VIA_URL"], cert=cert, data=data, headers=headers, timeout=60)
        return response


# Test to tests all process, detect, convert and retrieve file for output folder
class DocumentDetectConvertAndRetrieveTestCase(BaseTestCase):
    def test_detect_convert_retrieve_file(self):
        merge_lists = dep.filesNotConvertable + dep.filesConvertable
        for file in merge_lists:
            filename = file["fileName"]
            print("")
            print(f"--- TEST {filename} ---")
            print("")

            if self.via_run == "True":
                via_response = self.save_file_to_VIA(file["fileNameExt"], file["mimeType"])
                if via_response.status_code == 415:
                    continue
                self.assertEqual(via_response.status_code, 201)
                file["fileId"] = via_response.headers.get("Document-id")
                response = self.detection_file_type_via(file["fileId"])
            else:
                response = self.detection_file_type_n_via(file["fileNameExt"])
            json = response.json()
            print(f"get-file-type {filename}: " + str(json))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json["mimeType"], file["mimeType"])

            if self.via_run == "True":
                response = self.convert_file_via(file["fileId"], file["fileNameExt"])
            else:
                response = self.convert_file_n_via(file["fileNameExt"])
            json = response.json()
            print(f"convert {filename}: " + str(json))
            if response.status_code == 200:
                if json.get("status") in ["queued", "started"]:
                    task_id = json.get("taskId")
                    self.assertTrue(task_id)

                    ttl = 25
                    while ttl > 0:
                        time.sleep(1)
                        response = self.status_file(task_id)
                        json = response.json()
                        print(f"status {filename}: " + str(json))
                        self.assertEqual(response.status_code, 200)
                        if json.get("status") == "finished":
                            self.assertEqual(json, {
                                "taskId": task_id,
                                "status": "finished",
                                "fileType": "PDF/A",
                                "mimeType": "application/pdf",
                                "pdfVersion": "1B"
                            })
                            break
                        if json.get("status") == "failed":
                            self.fail("status failed - " + json.get("message"))
                        ttl -= 1

                    if self.via_run == "True":
                        # Download file with VIA
                        response = self.download_file(task_id)
                        self.assertEqual(response.status_code, 200)
                        json = response.json()
                        print(f"download {filename}: " + str(json))
                        self.assertEqual(json, {
                            "taskId": task_id,
                            "status": "finished",
                            "convertable": True,
                            "fileId": json.get("fileId"),
                            "fileType": "PDF/A",
                            "mimeType": "application/pdf",
                            "pdfVersion": "1B",
                            "fileName": file["fileName"] + ".pdf",
                            "fileSize": json.get("fileSize")
                        })

                        base_dir = os.path.abspath(os.path.dirname(__file__)+"/outputs")
                        file_dir = os.path.join(base_dir, json.get("fileName"))
                        via_response = get("{0}/{1}".format(self.app.config["VIA_URL"], json.get("fileId")), cert=self.app.config["VIA_CERT_PATH"], stream=True)     
                        self.assertEqual(via_response.status_code, 200)
                        with open(file_dir, "wb") as f:
                            for chunk in via_response.iter_content(chunk_size=128):
                                f.write(chunk)
                        exist_file = os.path.exists(file_dir)
                        self.assertEqual(exist_file, True)
                        self.assertIn(os.path.split(file_dir)[1], os.listdir(base_dir))
                    else:
                        base_dir = os.path.abspath(os.path.dirname(__file__) + "/outputs")
                        file_dir = os.path.join(base_dir, file["fileName"] + ".pdf")
                        response = self.download_file(task_id)
                        self.assertEqual(response.status_code, 200)
                        with open(file_dir, "wb") as f:
                            f.write(response.content)
                        exist_file = os.path.exists(file_dir)
                        self.assertEqual(exist_file, True)
                        self.assertIn(os.path.split(file_dir)[1], os.listdir(base_dir))
                else:
                    self.assertEqual(json,  {
                        "status": "non-convertable",
                        "fileType": file["fileType"],
                        "mimeType": file["mimeType"],
                        "pdfVersion": file["pdfVersion"] if "pdfVersion" in file else "",
                    })
