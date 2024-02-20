import logging
import ssl
import graypy
import socket

from logging.handlers import SocketHandler
from http.client import HTTPSConnection
from graypy.handler import BaseGELFHandler

class GraylogLogger(logging.LoggerAdapter):

    def __init__(self, name, config, facility):
        logging_cfg = config["LOGGING"]
        self.logger = logging.getLogger(name)
        self.setLevel(logging._checkLevel(logging_cfg["level"]))

        self.logger.addHandler(GelfHTTPHandler(host=config["GRAYLOG_HOST"], port=config["GRAYLOG_PORT"],
                                        path=config["GRAYLOG_PATH"], localname=config["GRAYLOG_SOURCE"], facility=facility))

        self.extra = { **logging_cfg["extra"] }

    def log(self, level, msg, request=None, extra= None, *args, **kwargs):
        if self.isEnabledFor(level):
            kwargs["extra"] = {**self.extra}
            if request:
                kwargs["extra"]["user"]= '%s - "%s"' % (request.remote_addr, request.user_agent.string)
                kwargs["extra"]["request"]= '%s - "%s"' % (request.method, request.path)
            if extra and isinstance(extra, dict):
                kwargs["extra"].update(extra)
            if level >= logging.ERROR:
                self.logger.error(level, msg, *args, **kwargs)
            else:
                self.logger.log(level, msg, *args, **kwargs)


class GelfHTTPHandler(BaseGELFHandler, logging.Handler):

    def __init__(self, host, port=12201, path='/gelf', timeout=5, fqdn=False, localname=None, facility=None, 
                 level_names=False, tls_cafile=None, tls_capath=None, tls_cadata=None,
                  tls_client_cert=None, tls_client_key=None, tls_client_password=None):
        BaseGELFHandler.__init__(self, host, port, fqdn=fqdn, localname=localname, facility=facility, level_names=level_names)
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
