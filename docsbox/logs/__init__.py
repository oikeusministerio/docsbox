import logging
import ssl
import socket
import sys

from http.client import HTTPSConnection
from graypy.handler import BaseGELFHandler
from flask.logging import default_handler


class GraylogLogger(logging.LoggerAdapter):

    def __init__(self, name, app, logtype):
        logging_cfg = app.config["LOGGING"]
        logger = logging.getLogger(name)
        logger.setLevel(logging._checkLevel(logging_cfg[logtype]["level"]))

        httpsHandler = GelfHTTPHandler(host=app.config["GRAYLOG_HOST"], port=app.config["GRAYLOG_PORT"],
                                        path=app.config["GRAYLOG_PATH"], localname=app.config["GRAYLOG_SOURCE"])
        logger.addHandler(httpsHandler)

        self.logger = logger
        self.extra = { **logging_cfg["extra"], **logging_cfg[logtype]["extra"]}

    def log(self, level, msg, extra= None, *args, **kwargs):
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
        try:
            self.connection = HTTPSConnection(self.host, self.port, context=ssl._create_unverified_context(), timeout=self.timeout)        
            self.connection.request('POST', self.path, data, headers={'Content-type': 'application/json'})
            self.connection.close()
        except:
            print("ERROR - Connection with Graylog was not possible, log was not sent.")