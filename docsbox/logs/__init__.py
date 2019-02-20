import logging
import ssl
import socket
import sys

from http.client import HTTPSConnection
from graypy.handler import BaseGELFHandler
from flask.logging import default_handler


class GraylogLogger(logging.LoggerAdapter):

    def __init__(self, name, graylog_cfg, logging_cfg):
        logger = logging.getLogger(name)
        logger.setLevel(logging._checkLevel(logging_cfg["level"]))

        httpsHandler = GelfHTTPHandler(host=graylog_cfg["host"], port=graylog_cfg["port"],
                                        path=graylog_cfg["path"], localname=graylog_cfg["localname"])
        logger.addHandler(httpsHandler)

        self.logger = logger
        self.extra = logging_cfg["extra"]

    def log(self, level, msg, extra= None, *args, **kwargs):
        level = logging._checkLevel(level)
        kwargs["extra"]= self.extra
        if extra:
            if "request" in extra:
                kwargs["extra"]["user"]= '%s - "%s"' % (extra["request"].remote_addr, extra["request"].user_agent.string)
                kwargs["extra"]["request"]= '%s - "%s"' % (extra["request"].method, extra["request"].path)
            if "status" in extra:
                kwargs["extra"]["status"]= extra["status"]

        if self.isEnabledFor(level):
            self.logger.log(level, msg, *args, **kwargs)


class GelfHTTPHandler(BaseGELFHandler, logging.Handler):

    def __init__(self, host, port=12201, path='/gelf', timeout=5, debugging_fields=False, fqdn=False, localname=None, facility=None, 
                 level_names=False, tls_cafile=None, tls_capath=None, tls_cadata=None,
                  tls_client_cert=None, tls_client_key=None, tls_client_password=None):
        BaseGELFHandler.__init__(self, host, port, debugging_fields=debugging_fields, fqdn=fqdn, localname=localname, facility=facility, level_names=level_names)
        logging.Handler.__init__(self)

        self.host = host
        self.port = port
        self.path = path
        self.timeout = timeout

    def emit(self, record):
        data = BaseGELFHandler.makePickle(self, record)

        self.connection = HTTPSConnection(self.host, self.port, context=ssl._create_unverified_context(), timeout=self.timeout)        
        self.connection.request('POST', self.path, data, headers={'Content-type': 'application/json'})
        self.connection.close()