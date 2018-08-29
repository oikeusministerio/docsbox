# Document Convertion

Service that allows you convert office documents, like .docx and .pptx, into more useful filetypes like PDF, for viewing it in browser with PDF.js, or HTML for organizing full-text search of document content.

`Document Convertion` is based on open source application **[docsbox]**.

# Install

```bash
$ git clone http://francnun@10.188.14.4:8888/scm/dk/common-conversion.git && cd common-conversion
$ docker-compose build
$ docker-compose up
```

# Test

Uploading File:
```bash
$ curl -X POST -F "file=@test.odt" http://localhost/api/document/upload
{"status": "queued", "id": "32982f1d-6b23-4360-b1aa-c324b538ac4c"}

$ curl -X POST -F "file=@test.docx" http://localhost/api/document/upload
{"message": "File cannot be uploaded needs to be converted"}
```

Checking File Type:
bash```
$ curl -X GET -F "file=@test.odt" http://localhost/api/document
{"mimetype": "application/vnd.oasis.opendocument.text"}
```

Converting and Retrieving a File:
```bash
$ curl -X POST -F "file=@test.docx" http://localhost/api/document/convert
{"status": "queued", "id": "146faa45-893b-4e3f-9251-d5f6dbeb5934"}

$ curl -X GET http://localhost/api/document/146faa45-893b-4e3f-9251-d5f6dbeb5934
{"status": "finished", "id": "146faa45-893b-4e3f-9251-d5f6dbeb5934"}

$ curl -X GET -O http://localhost/api/document/download/146faa45-893b-4e3f-9251-d5f6dbeb5934
```


# Supported Filetypes for conversion

| Type         | Format                    |
| -------------|---------------------------| 
| Document     | `doc` `docx` `odt` `rtf`  | 
| Presentation | `ppt` `pptx` `odp`        |
| Spreadsheet  | `xls` `xlsx` `ods`        | 
| XML          | `sxw` `stw` `sxc` `stc` `sxi` `sti` `sxd` `std` `sxm` |


[docsbox]: <https://travis-ci.org/dveselov/docsbox>