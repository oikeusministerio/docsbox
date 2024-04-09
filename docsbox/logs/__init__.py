import logging
import socket
import ssl

from graypy.handler import BaseGELFHandler


class GraylogLogger(logging.LoggerAdapter):

    def __init__(self, logger, config, facility):
        super().__init__(logger)
        logging_cfg = config["LOGGING"]
        self.setLevel(logging._checkLevel(logging_cfg["level"]))

        self.logger.addHandler(GelfTCPHandler(
            host=config["GRAYLOG_HOST"],
            port=config["GRAYLOG_PORT"],
            localname=config["GRAYLOG_SOURCE"],
            facility=facility))

        self.extra = {**logging_cfg["extra"]}

    def log(self, level, msg, request=None, extra=None, *args, **kwargs):
        if self.isEnabledFor(level):
            kwargs["extra"] = {**self.extra}
            if request:
                kwargs["extra"]["user"] = '%s - "%s"' % (request.remote_addr, request.user_agent.string)
                kwargs["extra"]["request"] = '%s - "%s"' % (request.method, request.path)
            if extra and isinstance(extra, dict):
                kwargs["extra"].update(extra)
            self.logger.log(level, msg, *args, **kwargs)


class GelfTCPHandler(BaseGELFHandler, logging.Handler):

    def __init__(self, host, port=12201, timeout=5, fqdn=False, localname=None, facility=None,
                 level_names=False, tls_cafile=None, tls_capath=None, tls_cadata=None,
                 tls_client_cert=None, tls_client_key=None, tls_client_password=None):
        BaseGELFHandler.__init__(
            self,
            fqdn=fqdn,
            localname=localname,
            facility=facility,
            level_names=level_names,
            compress=False)  # Compress needs to be false for TCP because of the null byte delimiter
        logging.Handler.__init__(self)

        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls_client_cert = tls_client_cert
        self.tls_client_key = tls_client_key
        self.tls_client_password = tls_client_password
        self.ssl_context = self.__create_ssl_context(tls_cafile, tls_capath, tls_cadata)
        self.socket = None

    def emit(self, record):
        data = BaseGELFHandler.makePickle(self, record)
        data += b'\x00'  # Null byte delimiter for GELF
        self.__send(data)

    def __send(self, data, attempt=1):
        try:
            self.__ensure_connected()
            self.socket.sendall(data)
        except (socket.error, ssl.SSLError) as e:
            print(f"ERROR - Graylog logging, connection issue, attempting to reconnect: {e}")
            self.__close_socket()
            if attempt == 1:
                self.__send(data, 2)
            else:
                raise e
        except Exception as e:
            print(f"ERROR - Graylog logging, unexpected error: {e}")
            self.__close_socket()

    def __create_ssl_context(self, cafile, capath, cadata):
        if cafile and capath and cadata:
            context = ssl.create_default_context(
                ssl.Purpose.SERVER_AUTH,
                cafile=cafile,
                capath=capath,
                cadata=cadata)
        else:
            context = ssl._create_unverified_context()
        if self.tls_client_cert and self.tls_client_key:
            context.load_cert_chain(
                certfile=self.tls_client_cert,
                keyfile=self.tls_client_key,
                password=self.tls_client_password)
        return context

    def __ensure_connected(self):
        if self.socket is None:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)

            # Enable TCP keep-alive on the socket
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            if hasattr(socket, 'TCP_KEEPIDLE'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60)
            if hasattr(socket, 'TCP_KEEPINTVL'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            if hasattr(socket, 'TCP_KEEPCNT'):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)

            self.socket = self.ssl_context.wrap_socket(sock, server_hostname=self.host)

        return self.socket

    def __close_socket(self):
        if self.socket:
            self.socket.close()
            self.socket = None
