import os
import ujson
import unittest
import docsbox
import time
import test_dependencies as dep
from requests import get

# SetUp/EndPoints
class BaseTestCase(unittest.TestCase):
    
    via_run = os.getenv('TEST_VIA')
    headers = {'Content-Disposition': ""}
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
        self.headers['Content-Disposition'] = fileName
        response = self.client.post("/conversion-service/convert/" + fileId, headers=self.headers)
        return response
    
    def convert_file_nVIA(self, filename):
        if filename:
            response = self.client.post("/conversion-service/convert/0", data={
                "file": (open(os.path.join(self.inputs, filename), "rb"), filename)
            })
        else:
            response = self.client.post("/conversion-service/convert/0")
        return response

    def convert_file_with_options_VIA(self, fileId, filename, options):
        self.headers['Content-Disposition'] = filename
        response = self.client.post("/conversion-service/convert/" + fileId, data={
            "options": ujson.dumps(options)
        }, headers=self.headers)
        return response

    def convert_file_with_options_nVIA(self, filename, options):
        response = self.client.post("/conversion-service/convert/0", data={
            "file": (open(os.path.join(self.inputs, filename), "rb"), filename),
            "options": ujson.dumps(options)
        })
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
        self.assertEqual(json.get("status"), "queued")
        
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
     
# Group of tests to test detection of type file and check if it's possible to convert
class DocumentDetectAndConvertTestCase(BaseTestCase):   

    def test_convert_empty_formats(self):
        if self.via_run == "True":
            response = self.convert_file_with_options_VIA(dep.filesConvertable[0]['fileId'], dep.filesConvertable[0]['fileName'], {
                "format": {},
            })
        else:
            response = self.convert_file_with_options_nVIA(dep.filesConvertable[0]['fileNameExt'], {
                "format": {}
            })
        json = ujson.loads(response.data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json, {
            "message": "Invalid 'format' value"
        })
    
    def test_convert_invalid_formats(self):
        if self.via_run == "True":
            response = self.convert_file_with_options_VIA(dep.filesConvertable[0]['fileId'], dep.filesConvertable[0]['fileName'], {
                "format": "csv",
            })
        else:
            response = self.convert_file_with_options_nVIA(dep.filesConvertable[0]['fileNameExt'], {
                "format": "csv",
            })
        json = ujson.loads(response.data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json, {
            "message": "'application/vnd.sun.xml.writer' mimetype can't be converted to 'csv'"
        })

    def test_detect_convert_file_not_convertable(self):
        for file in dep.filesNotConvertable:
            # Detect file type   
            if self.via_run == "True":
                response = self.detection_file_type_VIA(file['fileId'])
            else:    
                response = self.detection_file_type_nVIA(file['fileNameExt']) 
            json = ujson.loads(response.data)  
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json, {
                "fileType": file['fileType'],
                "convertable": False
            }) 

            # Convert file 
            if self.via_run == "True":
                response = self.convert_file_VIA(file['fileId'], file['fileName']) 
            else:
                response = self.convert_file_nVIA(file['fileNameExt']) 
            json = ujson.loads(response.data)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json,  {
                "status": "non-convertable",
                "fileType": file['mimeType']
            })
        
    def test_detect_convert_file(self):
        for file in dep.filesConvertable:            
            # Detect file type   
            if self.via_run == "True":
                response = self.detection_file_type_VIA(file['fileId'])
            else:
                response = self.detection_file_type_nVIA(file['fileNameExt']) 
            json = ujson.loads(response.data)  
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json, {
                "fileType": file['fileType'],
                "convertable": True
            }) 
            
            if self.via_run == "True":
                response = self.convert_file_VIA(file['fileId'], file['fileName']) 
            else:
                response = self.convert_file_nVIA(file['fileNameExt']) 
            json = ujson.loads(response.data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(json.get("taskId"))
            self.assertIsNotNone(json.get("status"))

            ttl = 15
            while (ttl > 0):
                time.sleep(2)
                response = self.status_file(json.get("taskId"))
                json = ujson.loads(response.data)
                self.assertEqual(response.status_code, 200)
                if (json.get("status") == "finished"):
                    self.assertEqual(ujson.loads(response.data), {
                    "taskId": json.get("taskId"),
                    "status": "finished",
                    "fileType": "PDF/A",
                    })
                    break 
   
# Test to tests all process, detect, convert and retrieve file for output folder
class DocumentDetectConvertAndRetrieveTestCase(BaseTestCase):
    def test_detect_convert_retrieve_file(self):
        mergeLists = dep.filesConvertable + dep.filesNotConvertable
        for file in mergeLists:       
            # Detect file type   
            if self.via_run == "True":
                response = self.detection_file_type_VIA(file['fileId'])
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
                response = self.convert_file_VIA(file['fileId'], file['fileName'])
            else:
                response = self.convert_file_nVIA(file['fileNameExt']) 
            json = ujson.loads(response.data)
            if response.status_code == 200:
                if isConvertable:
                    self.assertTrue(json.get("taskId"))
                    self.assertEqual(json.get("status"), "queued")

                    ttl = 50
                    while (ttl > 0):
                        time.sleep(5)
                        response = self.status_file(json.get("taskId"))
                        json = ujson.loads(response.data)
                        self.assertEqual(response.status_code, 200)
                        if (json.get("status") == "finished"):
                            self.assertEqual(ujson.loads(response.data), {
                            "taskId": json.get("taskId"),
                            "status": "finished",
                            "fileType": "PDF/A"
                            })
                            break
                        if (json.get("status") == "failed"):
                            self.fail()
                        ttl-=1

                    if self.via_run == "True":
                        # Download file with VIA
                        response = self.download_file(json.get("taskId"))
                        self.assertEqual(response.status_code, 200)
                        json = ujson.loads(response.data)
                        print(json)
                        self.assertEqual(ujson.loads(response.data), {
                            "status": "finished",
                            "fileId": json.get("fileId"),
                            "convertable": True,
                            "taskId": json.get("taskId"),
                            "fileType": "PDF/A",
                            "mimeType": "application/pdf",
                            "fileName": file['fileName'] + ".pdf"
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
                        response = self.download_file(json.get("taskId"))  
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
            elif response.status_code == 400:
                self.assertEqual(response.status_code, 400)
                self.assertEqual(json, {
                    "message": "File does not need to be converted."
                })  
            else:
                self.assertEqual(response.status_code, 415)
                split_mimetype = json.get("message").split(":")
                self.assertEqual(json, {
                    "message": "Not supported mimetype:"+split_mimetype[1]
                }) 
