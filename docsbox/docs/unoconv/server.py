import tempfile
import time
from subprocess import Popen
from pathlib import Path


class UnoServer:
    # Stripped down version from https://github.com/unoconv/unoserver/blob/master/src/unoserver/server.py

    def __init__(self, interface="127.0.0.1", port="2002"):
        self.interface = interface
        self.port = port
        self.tmp_uri = None
        self.process = self.start()

    def start(self, executable="soffice"):
        print("Starting unoserver")

        with tempfile.TemporaryDirectory() as tmpuserdir:
            connection = (
                "socket,host=%s,port=%s,tcpNoDelay=1;urp;StarOffice.ComponentContext"
                % (self.interface, self.port)
            )

            self.tmp_uri = Path(tmpuserdir).as_uri()

            cmd = [
                executable,
                "--headless",
                "--invisible",
                "--nocrashreport",
                "--nodefault",
                "--nologo",
                "--nofirststartwizard",
                "--norestore",
                f"-env:UserInstallation={self.tmp_uri}",
                f"--accept={connection}",
            ]

            print("Command: " + " ".join(cmd))
            process = Popen(cmd)

            pid = process.pid
            print(f"Server PID: {pid}")

            # Wait for startup
            time.sleep(10)

            return process
