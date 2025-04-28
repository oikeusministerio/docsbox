# docsbox [![Build Status](https://app.travis-ci.com/oikeusministerio/docsbox.svg?branch=master)](https://app.travis-ci.com/github/oikeusministerio/docsbox)

`docsbox` is a standalone service that allows you convert different types of files to PDF/A formats, including document, presentation, spreadsheet and image formats.

# Install and Start
Set the required configuration by copying the .env.example to .env and setting up the parameters accordingly.

```
docker build -t oikeusministerio/common-conversion:test docsbox
docker-compose up -d
```

# Configuration
The service can be configurable through the yml file `docsbox/config/config.yml`. These can be overridden with environment variables. Some examples:

```
REDIS_URL - Redis Server url (default: redis://redis:6379/0)
VIA_URL - VIA service url
VIA_CERT_PATH - Certificate path for VIA connection
VIA_ALLOWED_USERS - Allowed users for VIA
GRAYLOG_HOST - Graylog server (default: localhost)
GRAYLOG_PORT - Graylog server input port (default: 12001)
GRAYLOG_PATH - Graylog server input path (default: '/gelf')
GRAYLOG_SOURCE - Graylog name for the logger Host
```

# REST API
The conversion can be made using VIA or by sending the file appended to the request.

If there is no file appended the conversion service connects with VIA fileservice where requests the file with the given id. To test it will be needed some VIA file id

## File type
The service will read the file and return information of about it.

If used with VIA, it will respect the `Content-Type` header provided by VIA.
If it is not provided, the service will scan the file.

### Request
    POST    /conversion-service/get-file-type/{file_id}
    If used without VIA, set the file_id to 0 and send the file in request body

### Example response
    {
        convertable: true,
        fileType: "Microsoft Word 2007/2010 XML",
        mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        pdfVersion: ""
    }

### Types
| Type        | Description                                                                                                                                                                                                                                                                                          |
|-------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| convertable | `boolean` whether or not the service is able to convert the file. Will also be false if the file is already in PDF/A format                                                                                                                                                                          |
| fileType    | `string` a human-readable representation of the file's mimetype. Will be returned only if the file is convertable by the service, otherwise will return "Unknown/Corrupted". If the file is a PDF and is password protected, will return one of 'password-protected-partial' or 'password-protected' | 
| mimeType    | `string` the file's mimetype                                                                                                                                                                                                                                                                         |
| pdfVersion  | `string` PDF version, if the mimetype is `application/pdf`, otherwise empty. Will only be returned if the service scanned the file.                                                                                                                                                                  |

### Status codes
| Status | Description                                            |
|--------|--------------------------------------------------------|
| 200    | OK                                                     |
| 400    | No file or valid VIA file id was received              |
| 404    | File with the specified VIA file id was not found      |
| 500    | Unhandled server error                                 |
| 504    | Downloading file from VIA timed out                    |

## Convert
The service will queue the specified file to be converted.

If used with VIA, it will respect the `Content-Type` header provided by VIA. If it is not provided and the file is not previously scanned with the `get-file-type` API, the file will be scanned.
### Request
    POST    /conversion-service/v2/convert/{file_id}
    If used without VIA, set the file_id to 0 and send the file in request body

### Request headers
You may provide additional settings through headers, all of which are optional. 

| Header               | Description                                                                                                                              | Possible values                                  | Default |
|----------------------|------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------|---------|
| Conversion-Format    | One of the supported file types                                                                                                          | `["pdf", "docx", "xlsx", "pptx", "jpeg", "png"]` | `pdf`   |
| Output-Pdf-Version   | The PDF version you wish to receive                                                                                                      | `[1, 2, 3]`                                      | `1`     |
| Via-Allowed-Users    | If VIA is used, this will be the allowed users provided to VIA for a conversion result. This should be the CN of your client certificate | `example.com`                                    |         |
| Content-Disposition  | You may provide a filename for conversion service through this header                                                                    | `example.pdf`                                    |         |

### Example response
    {
        taskId: "123e4567-e89b-12d3-a456-426614174000",
        status: "queued"
    }

### Types
| Type       | Description                                                                                                                                                                  |
|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| taskId     | `string` UUID specific for this task, use this when polling the status of the conversion                                                                                     |
| status     | `string` `queued` or `started`                                                                                                                                               |

### Status codes
| Status | Description                                            |
|--------|--------------------------------------------------------|
| 200    | OK                                                     |
| 400    | No file or valid VIA file id was received              |
| 404    | File with the specified VIA file id was not found      |
| 500    | Unhandled server error                                 |
| 504    | Downloading file from VIA timed out                    |

## Status
Check the status of a conversion task with the task id.

### Request
    GET    /conversion-service/status/{task_id}

### Example responses
Successful

    {
        taskId: "123e4567-e89b-12d3-a456-426614174000",
        status: "finished",
        fileType: "PDF/A",
        mimeType: "application/pdf",
        pdfVersion: "1A",
    }

Queued

    {
        taskId: "123e4567-e89b-12d3-a456-426614174000",
        status: "queued",
    }

### Types
| Type       | Description                                                                                                                                                                                                                                                                                          |
|------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| taskId     | `string` UUID specific for this task, use this when polling the status of the conversion                                                                                                                                                                                                             |
| status     | `string` the status of the conversion, can be `queued`, `started`, `finished`, `failed`, `corrupted`, `non-convertable`                                                                                                                                                                              |
| fileType   | `string` a human-readable representation of the file's mimetype. Will be returned only if the file is convertable by the service, otherwise will return "Unknown/Corrupted". If the file is a PDF and is password protected, will return one of 'password-protected-partial' or 'password-protected' | 
| mimeType   | `string` the file's mimetype                                                                                                                                                                                                                                                                         |
| pdfVersion | `string` PDF version, if the mimetype is `application/pdf`, otherwise empty. Will only be returned if the service scanned the file.                                                                                                                                                                  |


### Status codes
| Status | Description                                  |
|--------|----------------------------------------------|
| 200    | OK                                           |
| 404    | No task with the specified task if was found |
| 500    | Unhandled server error                       |

## Download
If the conversion service used with VIA, the converted file will also be saved in VIA will return the VIA file if of the converted file.
If the file was sent directly to the conversion service, the converted file is sent when it's requested.

### Request
    GET    /conversion-service/get-converted-file/{task_id}

### Response
    {
        convertable: true,
        fileId: "0297b05c-5a8e-4c88-a6f2-649e3a971597",
        fileName: "example.pdf",
        mimeType: application/pdf,
        fileType: "PDF/A",
        pdfVersion: "1A",
        status: "finished",
        taskId: "123e4567-e89b-12d3-a456-426614174000",
        fileSize: 123456
    }

#### Without VIA
    Content-Type: application/pdf
    Content-Disposition: attachment; filename=example.pdf
    Body: file bytes

### Types
| Type        | Description                                                                                                                                                                                                                                                                                          |
|-------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| convertable | `boolean` always `true`                                                                                                                                                                                                                                                                              |
| fileType    | `string` a human-readable representation of the file's mimetype. Will be returned only if the file is convertable by the service, otherwise will return "Unknown/Corrupted". If the file is a PDF and is password protected, will return one of 'password-protected-partial' or 'password-protected' | 
| mimeType    | `string` the file's mimetype                                                                                                                                                                                                                                                                         |
| pdfVersion  | `string` PDF version, if the mimetype is `application/pdf`, otherwise empty. Will only be returned if the service scanned the file, meaning that                                                                                                                                                     |
| fileId      | `string` the file if with which the converted file can be downloaded with from VIA                                                                                                                                                                                                                   |
| taskId      | `string` UUID specific for this task, use this when polling the status of the conversion                                                                                                                                                                                                             |
| fileName    | `string` the file name                                                                                                                                                                                                                                                                               |
| pdfVersion  | `string` the PDF version of the converted file, if it was converted into a PDF                                                                                                                                                                                                                       |
| fileSize    | `number` the file size in bytes                                                                                                                                                                                                                                                                      |
| status      | `string` always `finished`                                                                                                                                                                                                                                                                           |

### Status codes
| Status | Description                                  |
|--------|----------------------------------------------|
| 200    | OK                                           |
| 404    | No task with the specified task if was found |
| 500    | Unhandled server error                       |

# Run tests
Tests can be run with VIA or without, if connection to VIA is not possible, TEST_VIA must be set to False when running tests.

The input files are saved in the /docsbox/docs/tests/inputs and the conversion outputs will be saved to the /docsbox/docs/tests/inputs directory.

```
TEST_VIA=False docker-compose -f docker-compose.yml -f docker-compose.test.yml up --exit-code-from test
```

# Supported source filetypes
| Type         | Format                                              | 
|--------------|-----------------------------------------------------|
| Document     | `.docx` `.doc` `.pages` `.rtf` `.pdf` `.sxw` `.odt` |
| Presentation | `.pptx` `.ppt` `.key` `.sxi` `.odp`                 |
| Spreadsheet  | `.xlsx` `.xls` `.numbers` `.sxc` `.ods`             |
| Images       | `.jpg` `.png` `.tiff` `.webp` `.heif` `.heic`       |
| Others       | `.sxd` `.sxg` `.odg`                                |
