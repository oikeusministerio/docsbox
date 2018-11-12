import os
import ujson
import unittest
import docsbox
import time
import test_dependencies as dep
from requests import get

# SetUp/EndPoints
class BaseTestCase(unittest.TestCase):

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
    def detection_file_type(self, fileId):
        response = self.client.get("/conversion-service/get-file-type/" + fileId)
        return response

    # Convert File
    def convert_file(self, fileId, fileName):
        self.headers['Content-Disposition'] = fileName
        response = self.client.post("/conversion-service/convert/" + fileId, headers=self.headers)
        return response
    
    # Convert File with Options
    def convert_file_with_options(self, fileId, fileName, options):
        self.headers['Content-Disposition'] = fileName
        response = self.client.post("/conversion-service/convert/" + fileId, data={
            "options": ujson.dumps(options)
        }, headers=self.headers)
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
        response = self.convert_file(dep.filesConvertable[0]['fileId'], dep.filesConvertable[0]['fileName']) 
        json = ujson.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.get("taskId"))
        self.assertEqual(json.get("status"), "queued")
        
        time.sleep(3)

        response = self.status_file(json.get("taskId"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ujson.loads(response.data), {
            "taskId": json.get("taskId"),
            "status": "finished",
            "fileType": "application/pdf"
        })

    def test_get_task_by_invalid_uuid(self):
        response = self.convert_file("8c286c7f-ce38-4693-1234-e5d2ab3ce595", "unknown") 
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ujson.loads(response.data), {
            "message": "8c286c7f-ce38-4693-1234-e5d2ab3ce595. You have requested this URI [/conversion-service/convert/8c286c7f-ce38-4693-1234-e5d2ab3ce595] but did you mean /conversion-service/convert/<file_id> ?"
        })    
  
# Test to test the deletion of temporary files
class DocumentDeleteTemporaryFilesTestCase(BaseTestCase):
    def test_delete_temporary_file(self):
        response = self.convert_file(dep.filesConvertable[0]['fileId'], dep.filesConvertable[0]['fileName']) 
        json = ujson.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.get("taskId"))
        self.assertEqual(json.get("status"), "queued")
        
        time.sleep(3)

        response_delete_tmpFile = self.delete_temporary_file(json.get("taskId"))
        json_delete_tmpFile = ujson.loads(response_delete_tmpFile.data)
        self.assertEqual(response_delete_tmpFile.status_code, 200)
        self.assertEqual(json_delete_tmpFile, "finished")
       
        response_status_file = self.delete_temporary_file(json.get("taskId"))
        json_status_file = ujson.loads(response_status_file.data)
        self.assertEqual(response_status_file.status_code, 400)
        self.assertEqual(json_status_file, {
            "message": "Task is finished"
        })       

# Group of tests to test detection of type file and check if it's possible to convert
class DocumentDetectAndConvertTestCase(BaseTestCase):   
    def test_convert_invalid_mimetype(self):
        response = self.convert_file(dep.filesUnknown[0]['fileId'], dep.filesUnknown[0]['fileName']) 
        json = ujson.loads(response.data)
        self.assertEqual(response.status_code, 415)
        self.assertEqual(json, {
            "message": "Not supported mimetype: '"+dep.filesUnknown[0]['fileType']+"'"
        })
    
    def test_convert_empty_formats(self):
        response = self.convert_file_with_options(dep.filesConvertable[0]['fileId'], dep.filesConvertable[0]['fileName'], {
            "formats": [],
        })
        json = ujson.loads(response.data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json, {
            "message": "Invalid 'formats' value"
        })
    
    def test_convert_invalid_formats(self):
        response = self.convert_file_with_options(dep.filesConvertable[0]['fileId'], dep.filesConvertable[0]['fileName'], {
            "formats": ["csv"],
        })
        json = ujson.loads(response.data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json, {
            "message": "'application/vnd.sun.xml.writer' mimetype can't be converted to 'csv'"
        })
    
    def test_detect_convert_file_not_required(self):
        for file in dep.filesNotConvertable:
            # Detect file type   
            response = self.detection_file_type(file['fileId'])
            json = ujson.loads(response.data)  
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json, {
                "fileType": file['fileType'],
                "convertable": False
            }) 

            # Convert file 
            response = self.convert_file(file['fileId'], file['fileName']) 
            json = ujson.loads(response.data)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(json, {
                'message': 'File does not need to be converted.'
            })
     
    def test_detect_convert_file_required(self):
        for file in dep.filesConvertable:            
            # Detect file type   
            response = self.detection_file_type(file['fileId'])
            json = ujson.loads(response.data)  
            self.assertEqual(response.status_code, 200)
            self.assertEqual(json, {
                "fileType": file['fileType'],
                "convertable": True
            }) 
            
            response = self.convert_file(file['fileId'], file['fileName']) 
            json = ujson.loads(response.data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(json.get("taskId"))
            self.assertEqual(json.get("status"), "queued")

            ttl = 10
            while (ttl > 0):
                time.sleep(2)
                response = self.status_file(json.get("taskId"))
                json = ujson.loads(response.data)
                self.assertEqual(response.status_code, 200)
                if (json.get("status") == "finished"):
                    self.assertEqual(ujson.loads(response.data), {
                    "taskId": json.get("taskId"),
                    "status": "finished",
                    "fileType": "application/pdf"
                    })
                    break 
     
# Test to tests all process, detect, convert and retrieve file for output folder
class DocumentDetectConvertAndRetrieveTestCase(BaseTestCase):
    def test_detect_convert_retrieve_file(self):
        mergeLists = dep.filesConvertable + dep.filesUnknown + dep.filesNotConvertable
        for file in mergeLists:       
            # Detect file type   
            response = self.detection_file_type(file['fileId'])
            json = ujson.loads(response.data)  

            self.assertEqual(response.status_code, 200)
            if json.get("convertable"):
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
            response = self.convert_file(file['fileId'], file['fileName'])
            json = ujson.loads(response.data)
            
            if response.status_code == 200:
                self.assertTrue(json.get("taskId"))
                self.assertEqual(json.get("status"), "queued")
                    
                ttl = 10
                while (ttl > 0):
                    time.sleep(2)
                    response = self.status_file(json.get("taskId"))
                    json = ujson.loads(response.data)
                    self.assertEqual(response.status_code, 200)
                    if (json.get("status") == "finished"):
                        self.assertEqual(ujson.loads(response.data), {
                        "taskId": json.get("taskId"),
                        "status": "finished",
                        "fileType": "application/pdf"
                        })
                        break 

                # Download file 
                response = self.download_file(json.get("taskId"))      
                self.assertEqual(response.status_code, 200)
                json = ujson.loads(response.data)
                print(json)
                self.assertEqual(ujson.loads(response.data), {
                    "status": "finished",
                    "fileId": json.get("fileId"),
                    "convertable": True,
                    "taskId": json.get("taskId"),
                    "fileType": "application/pdf",
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

            elif response.status_code == 400:
                self.assertEqual(response.status_code, 400)
                self.assertEqual(json, {
                    'message': 'File does not need to be converted.'
                })  
            else:
                self.assertEqual(response.status_code, 415)
                split_mimetype = json.get("message").split(":")
                self.assertEqual(json, {
                    "message": "Not supported mimetype:"+split_mimetype[1]
                }) 
