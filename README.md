# docsbox [![Build Status](https://travis-ci.org/oikeusministerio/docsbox.svg?branch=master)](https://travis-ci.org/oikeusministerio/docsbox)

`docsbox` is a standalone service that allows you convert office documents, like .docx and .pptx, into PDF/A, for viewing it in browser with PDF.js, or HTML for organizing full-text search of document content.  
`docsbox` uses **LibreOffice** 6.1 (via **LibreOfficeKit**) for document converting.

# Install and Start
Currently, installing powered by docker-compose:

```
1 - git clone https://github.com/oikeusministerio/docsbox.git
2 - cd docsbox
3 - docker-compose build
4 - docker-compose up
```

It'll start this services:

```bash
$ docker ps
CONTAINER ID  IMAGE                                      COMMAND                 CREATED             STATUS             PORTS                   NAMES
f6b55773c71d  oikeusministerio/common-conversion:latest  "rq worker -c docsbox"  About a minute ago  Up About a minute                          docsbox_rqworker_1
662b08daefea  oikeusministerio/common-conversion:latest  "rqscheduler -H redis"  About a minute ago  Up About a minute                          docsbox_rqscheduler_1
0364df126b36  oikeusministerio/common-conversion:latest  "gunicorn -b :8000 do"  About a minute ago  Up About a minute  0.0.0.0:8000->8000/tcp  docsbox_web_1
7ce674173732  docsbox_nginx                              "/usr/sbin/nginx"       About a minute ago  Up About a minute  0.0.0.0:80->80/tcp      docsbox_nginx_1
5e8c8481e288  redis:latest                               "docker-entrypoint.sh"  About a minute ago  Up About a minute  0.0.0.0:6379->6379/tcp  docsbox_redis_1
```

# Settings (env)
```
REDIS_URL - Redis Server url (default: redis://redis:6379/0)

VIA_URL - VIA service url (default: https://it1.integraatiopalvelu.fi/Tallennuspalvelu)
VIA_CERT_PATH - Certificate path for VIA connection (default: /home/docsbox/certificate.pem)
VIA_ALLOWED_USERS - Allowed users for VIA (default: sampotesti)

GRAYLOG_HOST - Graylog server (default: localhost)
GRAYLOG_PORT - Graylog server input port (default: 12001)
GRAYLOG_PATH - Graylog server input path (default: '/gelf')
GRAYLOG_SOURCE - Graylog name for the logger Host
```

# Configuration
The service can be configurable through the yml file `docsbox/config/config.yml`.

# Test
The conversion can be made using VIA or by sending the file appended to the request.

If there is no file appended the conversion service connects with VIA fileservice where requests the file with the given id. To test it will be needed some VIA file id

Checking File Type:
```bash
$ curl -X POST -F "file=@test.doc" http://localhost/conversion-service/get-file-type/0
{
    "fileType": "Microsoft Word",
    "convertable": true
}
```
```bash
$ curl -X POST http://localhost/conversion-service/get-file-type/02127a06-d078-4935-a6f9-b7cbdbff4959
{
    "fileType": "Microsoft Word",
    "convertable": true
}
```
```bash
curl -X POST -F "file=@test6.odt" http://localhost/conversion-service/convert/0
{
    "message": "File does not need to be converted."
}
```
```bash
$ curl -X POST http://localhost/conversion-service/get-file-type/0123456789
{
    "message": "No file has sent nor valid file_id given."
}
```

Request conversion & checking conversion status:
```bash
$ curl -X POST -F "file=@test.doc" http://localhost/conversion-service/convert/0
{
    "taskId": "bbf78afd-011c-4815-95da-17b810fa4f5f",
    "status": "queued"
}
```
```bash
$ curl -X POST --header "Content-Disposition: filename.doc" http://localhost/conversion-service/convert/02127a06-d078-4935-a6f9-b7cbdbff4959
{
    "taskId": "bbf78afd-011c-4815-95da-17b810fa4f5f",
    "status": "queued"
}
```
```bash
$ curl -X POST http://localhost/conversion-service/convert/0123456789
{
    "message": "No file has sent nor valid file_id given."
}
```
```bash
$ curl -X GET http://localhost/conversion-service/status/bbf78afd-011c-4815-95da-17b810fa4f5f
{
    "fileType": "PDF/A",
    "taskId": "bbf78afd-011c-4815-95da-17b810fa4f5f",
    "status": "finished"
}
```

If the conversion service used a VIA file the converted file also will be saved in VIA and returns the new file id.
If the file was sent directly to the conversion service, the converted file is sent when its requested 

Request converted file:
```bash
$ curl -X GET http://localhost/conversion-service/get-converted-file/bbf78afd-011c-4815-95da-17b810fa4f5f
{
    "convertable": true,
    "fileId": "92180232-5d1a-456f-80d7-2cbc596afb57",
    "fileName": "filename.pdf",
    "mimeType": "application/pdf",
    "fileType": "PDF/A",
    "status": "finished",
    "taskId": "bbf78afd-011c-4815-95da-17b810fa4f5f"
    "fileSize": "80325"
}
```
```bash
$ curl -X GET -O http://localhost/conversion-service/get-converted-file/bbf78afd-011c-4815-95da-17b810fa4f5f
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   212  100   212    0     0  15142      0 --:--:-- --:--:-- --:--:-- 15142


```

Its is possible to request the deletion of the temp converted file as:
```bash
$ curl -X DELETE http://localhost/conversion-service/delete-tmp-file/bbf78afd-011c-4815-95da-17b810fa4f5f
"finished"
```

# API
```
POST    /conversion-service/get-file-type/{file_id}

POST   /conversion-service/convert/{file_id}

GET    /conversion-service/status/{task_id}

GET    /conversion-service/get-converted-file/{task_id}

DELETE /conversion-service/delete-tmp-file/{task_id}
```

# Scaling
Within a single physical server, docsbox can be scaled by docker-compose:
```bash
$ docker-compose scale web=4 rqworker=8
```
The Application implements possibility for multi-host deployment using Docker Swarm it will be need the creation of a global syncronized volume (e.g. with flocker), global redis-server and mount it at `docker-compose.yml` file.


# Run tests (Ubuntu)
Tests can be run with VIA or without, if connection to VIA is not possible, TEST_VIA must be set to False when running tests.

```
1 - cd docsbox
2 - docker-compose build
3 - sudo TEST_VIA=False docker-compose -f docker-compose.yml -f docker-compose.test.yml up --exit-code-from test
4 - The tests are run on the docker container and the run result is returned on the console
5 - Folder Inputs to input files for conversion
6 - Folder Outputs to output the converted files
```

# Supported filetypes
| Type           | Format                                            | 
| ---------------|-------------------------------------------------- |
| Document       | `.docx` `.doc` `.kth` `.rtf` `.pdf` `.sxw` `.odt` |
| Presentation   | `.pptx` `.ppt` `.pages` `.sxi` `.odp`             |
| Spreadsheet    | `.xlsx` `.xls` `.numbers` `.sxc` `.ods`           |
| Others         | `.sxd` `.sxg` `.odg`                              |
