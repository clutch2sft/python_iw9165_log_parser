from paramiko import SFTPHandle, SFTPServer,  SFTP_OK
from pydispatch import dispatcher

class StubSFTPHandle(SFTPHandle):
    def __init__(self, fs, path, logger):
        super(StubSFTPHandle, self).__init__()
        self.fs = fs
        self.path = path
        self.logger = logger

    def close(self):
        # Check if the file was opened for writing or appending
        if 'w' in self.readfile.mode or 'a' in self.readfile.mode:
            self.logger.info(f"File closed after write: {self.path}")
            # Emit event with the path of the file received
            dispatcher.send(signal="FileReceived", sender=self, path=self.path,  fs=self.fs, logger=self.logger)
        super(StubSFTPHandle, self).close()

    def stat(self):
        try:
            info = self.fs.getinfo(self.path, namespaces=['stat'])
            return SFTPHandle.from_stat(info.raw['stat'])
        except OSError as e:
            self.logger.error(f"Failed to stat {self.path}: {e}")
            return SFTPServer.convert_errno(e.errno)

    def chattr(self, attr):
        try:
            permissions = getattr(attr, 'st_mode', None)
            if permissions:
                self.fs.setinfo(self.path, {'details': {'permissions': permissions}})
            return SFTP_OK
        except OSError as e:
            self.logger.error(f"Failed to change attributes for {self.path}: {e}")
            return SFTPServer.convert_errno(e.errno)
