# docsbox [![Build Status](https://app.travis-ci.com/oikeusministerio/docsbox.svg?branch=master)](https://app.travis-ci.com/github/oikeusministerio/docsbox)

`docsbox` is a standalone service that allows you convert different types of files to PDF/A formats, including document, presentation, spreadsheet and image formats.

# Install and Start
Set the required configuration by copying the .env.example to .env and setting up the parameters accordingly.

```
docker build -t oikeusministerio/common-conversion:test docsbox
docker-compose up -d
```

# Settings
The service can be configurable through the yml file `docsbox/config/config.yml`. These can be overridden with Docker environment variables. Some examples:

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

# REST API
The conversion can be made using VIA or by sending the file appended to the request.

If there is no file appended the conversion service connects with VIA fileservice where requests the file with the given id. To test it will be needed some VIA file id

## Checking File Type

### Request
    POST    /conversion-service/get-file-type/{file_id}
    
### Response
    Content-Type: application/json
    
    {
        convertable: [true, false],
        fileType: [Unknown/Corrupted, PDF/A, Microsoft Word, ...]
    }

fileType = 'Unknown/Corrupted' when mimetype library cannot identify file type. 
    
### Error Responses
    400 - message: No file has sent nor valid file_id given.
    404 - message: File id was not found.
    504 - message: VIA service took too long to respond.

### Examples:
```
$ curl -X POST -F "file=@test.doc" http://localhost/conversion-service/get-file-type/0
{
    "fileType": "Microsoft Word",
    "convertable": true
}
```
```
$ curl -X POST http://localhost/conversion-service/get-file-type/02127a06-d078-4935-a6f9-b7cbdbff4959
{
    "fileType": "Microsoft Word",
    "convertable": true
}
```
```bash
$ curl -X POST http://localhost/conversion-service/get-file-type/0123456789
{
    "message": "No file has sent nor valid file_id given."
}
```

## Convert File

### Request
    POST    /conversion-service/v2/convert/{file_id}
    
    Headers:    Conversion-Format: [pdf, docx, xlsx, pptx, jpeg, png] (default: pdf)
                Output-Pdf-Version: [1, 2] (default: 1)
                Via-Allowed-Users: (VIA user allowed to download converted file, only used if using VIA file ID)
                Content-Disposition: filename (only used if using VIA file ID)
    
### Response
    Content-Type: application/json
    
    {
        taskId: task_id,
        status: [queued, started]
    }

There is a possibilty that convert request can give status as 'started' if worker is available immediately.
    
### Error Responses
    400 - message: No file has sent nor valid file_id given.
    404 - message: File id was not found.
    504 - message: VIA service took too long to respond.

### Examples:
```bash
$ curl -X POST -F "file=@test.doc" http://localhost/conversion-service/v2/convert/0
{
    "taskId": "bbf78afd-011c-4815-95da-17b810fa4f5f",
    "status": "queued"
}
```
```bash
$ curl -X POST --header "Content-Disposition: filename.doc" http://localhost/conversion-service/v2/convert/02127a06-d078-4935-a6f9-b7cbdbff4959
{
    "taskId": "bbf78afd-011c-4815-95da-17b810fa4f5f",
    "status": "queued"
}
```
```bash
$ curl -X POST http://localhost/conversion-service/v2/convert/0123456789
{
    "message": "No file has sent nor valid file_id given."
}
```
```bash
$ curl -X POST -H 'Output-Pdf-Version: 2' -F 'file=@"test.doc"' http://localhost/conversion-service/v2/convert/0
{
    "taskId": "bbf78afd-011c-4815-95da-17b810fa4f5f",
    "status": "queued"
}
```

## Task Status

### Request
    GET    /conversion-service/status/{task_id}
    
### Response
    Content-Type: application/json
    
    {
        taskId: task_id,
        status: [queued, started, finished, failed]
        fileType: [PDF/A, Microsoft Word 2007/2010 XML, ...] (only given if task finished)
    }
    
Status request response when conversion fails, will return status as 'failed' and send to graylog the error stacktrace.

### Error Responses
    404 - message: Unknown task_id.

### Example:
```bash
$ curl -X GET http://localhost/conversion-service/status/bbf78afd-011c-4815-95da-17b810fa4f5f
{
    "fileType": "PDF/A",
    "taskId": "bbf78afd-011c-4815-95da-17b810fa4f5f",
    "status": "finished"
}
```

## Get Converted File

If the conversion service used a VIA file the converted file also will be saved in VIA and returns the new file id.
If the file was sent directly to the conversion service, the converted file is sent when its requested

### Request
    GET    /conversion-service/get-converted-file/{task_id}
    
### Response
#### Using VIA
    Content-Type: application/json

    {
        convertable: true,
        fileId: via_file_id,
        fileName: filename,
        mimeType: [application/pdf, application/vnd.openxmlformats-officedocument.wordprocessingml.document, ...],
        fileType: [PDF/A, Microsoft Word 2007/2010 XML, ...],
        status: finished,
        taskId: task_id
        fileSize: converted file size in bytes
    }
    
#### Without VIA
    Content-Type: {file_mimetype}
    Content-Disposition: attachment; filename={filename}
    Body: Raw Data

### Error Responses
    404 - message: Unknown task_id.

### Examples:
##### Using VIA file ID for conversion.
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
##### Non VIA conversion
```bash
$ curl -X GET -O http://localhost/conversion-service/get-converted-file/bbf78afd-011c-4815-95da-17b810fa4f5f
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
100   212  100   212    0     0  15142      0 --:--:-- --:--:-- --:--:-- 15142
```

# Scaling
Within a single physical server, docsbox can be scaled by docker-compose:
```bash
$ docker-compose scale rqworker=8
```
In order to scale to multiple hosts, the hosts need a shared disk and a shared redis. The application does not support a redis cluster.


# Run tests
Tests can be run with VIA or without, if connection to VIA is not possible, TEST_VIA must be set to False when running tests.

The input files are saved in the /docsbox/docs/tests/inputs and the conversion outputs will be saved to the /docsbox/docs/tests/inputs directory.

```
TEST_VIA=False docker-compose -f docker-compose.yml -f docker-compose.test.yml up --exit-code-from test
```

# Supported filetypes
| Type           | Format                                              | 
| ---------------|-----------------------------------------------------|
| Document       | `.docx` `.doc` `.pages` `.rtf` `.pdf` `.sxw` `.odt` |
| Presentation   | `.pptx` `.ppt` `.key` `.sxi` `.odp`                 |
| Spreadsheet    | `.xlsx` `.xls` `.numbers` `.sxc` `.ods`             |
| Images         | `.jpg` `.png` `.tiff` `.webp` `.heif` `.heic`       |
| Others         | `.sxd` `.sxg` `.odg`                                |
