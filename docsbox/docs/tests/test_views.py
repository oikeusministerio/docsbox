import os
import ujson
import unittest
import docsbox
import time
import test_dependencies as dep
from requests import get, post

# SetUp/EndPoints
class BaseTestCase(unittest.TestCase):

    via_run = os.getenv('TEST_VIA')

    def setUp(self):
        self.app = docsbox.app
        self.app.config["TESTING"] = True
        self.app.config["RQ_ASYNC"] = False
        self.inputs = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),"inputs/"
        )
        self.client = docsbox.app.test_client()

    # Check File Type
    def detection_file_type_VIA(self, fileId):
        response = self.client.post("/conversion-service/get-file-type/" + fileId)
        return response

    def detection_file_type_nVIA(self, filename):
        response = self.client.post("/conversion-service/get-file-type/0", data={
            "file": (open(os.path.join(self.inputs, filename), "rb"), filename)
        })
        return response

    # Convert File
    def convert_file_VIA(self, fileId, fileName):
        response = self.client.post("/conversion-service/convert/" + fileId, headers={'Content-Disposition':fileName, 'Via-Allowed-Users':'test'})
        return response

    def convert_file_nVIA(self, filename):
        if filename:
            response = self.client.post("/conversion-service/convert/0", data={
                "file": (open(os.path.join(self.inputs, filename), "rb"), filename)
            })
        else:
            response = self.client.post("/conversion-service/convert/0")
        return response

    def convert_file_with_options_VIA(self, fileId, headers):
        response = self.client.post("/conversion-service/convert/" + fileId, headers=headers)
        return response

    def convert_file_with_options_nVIA(self, filename, headers):
        response = self.client.post("/conversion-service/convert/0", data={
            "file": (open(os.path.join(self.inputs, filename), "rb"), filename)}, headers=headers)
        return response

    # File Status
    def status_file(self, taskId):
        response = self.client.get("/conversion-service/status/" + taskId)
        return response

    # Download File
    def download_file(self, taskId):
        response = self.client.get("/conversion-service/get-converted-file/" + taskId)
        return response

    # Delete Temporary Files
    def delete_temporary_file(self, taskId):
        response = self.client.delete("/conversion-service/delete-tmp-file/" + taskId)
        return response

    # Save File to VIA
    def save_file_to_VIA(self, filename, mime_type):
        with open(os.path.join(self.inputs, filename), "rb") as data:
            cert = self.app.config["VIA_CERT_PATH"]
            headers = { 'VIA_ALLOWED_USERS': self.app.config["VIA_ALLOWED_USERS"], 'Content-type': mime_type }
            response = post(url=self.app.config["VIA_URL"], cert=cert, data=data, headers=headers, timeout=60)
        return response

# Group of tests to test valid or invalid UUID
class DocumentUUIDTestCase(BaseTestCase):
    def test_get_task_by_valid_uuid(self):
        if self.via_run == "True":
            response = self.convert_file_VIA(dep.filesConvertable[0]['fileId'], dep.filesConvertable[0]['fileName']) 
        else:
            response = self.convert_file_nVIA(dep.filesConvertable[0]['fileNameExt']) 
        json = ujson.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.get("taskId"))
        self.assertIn(json.get("status"), {"queued", "started"})

        time.sleep(5)

        response = self.status_file(json.get("taskId"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ujson.loads(response.data), {
            "taskId": json.get("taskId"),
            "status": "finished",
            "fileType": "PDF/A"
        })
    '''
    def test_get_task_by_invalid_uuid(self):
        # response = self.convert_file_VIA("8c286c7f-ce38-4693-1234-e5d2ab3ce595", "unknown") 
        response = self.client.post("/conversion-service/convert/uuid-with-ponies")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ujson.loads(response.data), {
            "message": "8c286c7f-ce38-4693-1234-e5d2ab3ce595. You have requested this URI [/conversion-service/convert/8c286c7f-ce38-4693-1234-e5d2ab3ce595] but did you mean /conversion-service/convert/<file_id> ?"
        })   
    '''
     

# Test to tests all process, detect, convert and retrieve file for output folder
class DocumentDetectConvertAndRetrieveTestCase(BaseTestCase):
    def test_detect_convert_retrieve_file(self):
        mergeLists = dep.filesConvertable + dep.filesNotConvertable
        for file in mergeLists:       
            # Detect file type   
            if self.via_run == "True":
                via_response = self.save_file_to_VIA(file['fileNameExt'], file['mimeType'])
                if (via_response.status_code == 415) :
                    continue
                self.assertEqual(via_response.status_code, 201)
                file["fileId"] = via_response.headers.get("Document-id")
                response = self.detection_file_type_VIA(file["fileId"])
            else:
                response = self.detection_file_type_nVIA(file['fileNameExt']) 
            json = ujson.loads(response.data)  

            self.assertEqual(response.status_code, 200)

            isConvertable = json.get("convertable")
            if isConvertable:
                self.assertEqual(json, {
                    "fileType": file['fileType'],
                    "convertable": True
                })
            else:
                self.assertEqual(json, {
                    "fileType": file['fileType'],
                    "convertable": False
                })

            # Convert file
            if self.via_run == "True":
                response = self.convert_file_VIA(file['fileId'], file['fileNameExt'])
            else:
                response = self.convert_file_nVIA(file['fileNameExt'])
            json = ujson.loads(response.data)
            if response.status_code == 200:
                if isConvertable:
                    taskId = json.get("taskId")
                    self.assertTrue(taskId)
                    self.assertIn(json.get("status"), {"queued", "started"})

                    ttl = 25
                    while (ttl > 0):
                        time.sleep(10)
                        response = self.status_file(taskId)
                        json = ujson.loads(response.data)
                        self.assertEqual(response.status_code, 200)
                        if (json.get("status") == "finished"):
                            self.assertEqual(ujson.loads(response.data), {
                            "taskId": taskId,
                            "status": "finished",
                            "fileType": "PDF/A"
                            })
                            break
                        if (json.get("status") == "failed"):
                            self.fail("status failed - " + json.get("message"))
                        ttl-=1

                    if self.via_run == "True":
                        # Download file with VIA
                        response = self.download_file(taskId)
                        self.assertEqual(response.status_code, 200)
                        json = ujson.loads(response.data)
                        self.assertEqual(json, {
                            "taskId": taskId,
                            "status": "finished",
                            "convertable": True,
                            "fileId": json.get("fileId"),
                            "fileType": "PDF/A",
                            "mimeType": "application/pdf",
                            "fileName": file['fileName'] + ".pdf",
                            "fileSize": json.get("fileSize")
                        })

                        base_dir = os.path.abspath(os.path.dirname(__file__)+'/outputs')
                        file_dir = os.path.join(base_dir, json.get("fileName"))
                        via_response = get("{0}/{1}".format(self.app.config["VIA_URL"], json.get("fileId")), cert=self.app.config["VIA_CERT_PATH"], stream=True)     
                        self.assertEqual(via_response.status_code, 200)
                        with open(file_dir, "wb") as file:
                            for chunk in via_response.iter_content(chunk_size=128):
                                file.write(chunk)
                        existFile = os.path.exists(file_dir)
                        self.assertEqual(existFile, True)
                        self.assertIn(os.path.split(file_dir)[1], os.listdir(base_dir))
                    else:
                        # Download file nVIA
                        base_dir = os.path.abspath(os.path.dirname(__file__)+'/outputs')
                        file_dir = os.path.join(base_dir, file['fileName']+".pdf")
                        response = self.download_file(taskId)  
                        self.assertEqual(response.status_code, 200)
                        with open(file_dir, "wb") as file:
                            file.write(response.data)
                        existFile = os.path.exists(file_dir)
                        self.assertEqual(existFile, True)
                        self.assertIn(os.path.split(file_dir)[1], os.listdir(base_dir))
                else:
                    self.assertEqual(json,  {
                        "status": "non-convertable",
                        "fileType": file['mimeType']
                    })
