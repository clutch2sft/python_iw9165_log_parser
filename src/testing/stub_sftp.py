# Copyright (C) 2003-2009  Robey Pointer <robeypointer@gmail.com>
#
# This file is part of paramiko.
#
# Paramiko is free software; you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# Paramiko is distrubuted in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Paramiko; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA.

"""
A stub SFTP server for loopback SFTP testing.
"""

import os, io, errno
from stat import S_IFDIR, S_IFREG
from paramiko import ServerInterface, SFTPServerInterface, SFTPServer, SFTPAttributes, \
    SFTPHandle, SFTP_OK, AUTH_SUCCESSFUL, OPEN_SUCCEEDED
import logging
from InMemoryFileSystem import InMemoryFileSystem

class StubServer (ServerInterface):
    def check_auth_password(self, username, password):
        # all are allowed
        return AUTH_SUCCESSFUL

    def check_auth_publickey(self, username, key):
        # all are allowed
        return AUTH_SUCCESSFUL

    def check_channel_request(self, kind, chanid):
        return OPEN_SUCCEEDED

    def get_allowed_auths(self, username):
        """List availble auth mechanisms."""
        return "password,publickey"


class StubSFTPHandle(SFTPHandle):
    def __init__(self, flags):
        self.flags = flags
        self.mode = 'r+'  # default mode, you can adjust based on flags
        # Set mode based on flags
        if flags & os.O_WRONLY:
            self.mode = 'w'
        elif flags & os.O_RDWR:
            self.mode = 'r+'
        if flags & os.O_APPEND:
            self.mode = 'a'  # handle append separately

    def read(self, length):
        return self.file_obj.read(length)

    def write(self, offset, data):
        try:
            logging.debug(f"Attempting to write to file: {self.filename} with mode: {self.mode}")
            if 'w' in self.mode or 'a' in self.mode:
                # Assumption: file_obj supports writing at a specific offset
                self.writefile.seek(offset)  # Position the file pointer
                self.writefile.write(data)
                self.writefile.flush()  # Ensure data is written to disk
                written_bytes = len(data)
                logging.debug(f"Written {written_bytes} bytes to file: {self.filename}")
                return written_bytes
            else:
                logging.error("Write operation not allowed due to file mode restrictions")
                return SFTPServer.convert_errno(errno.EBADF)
        except Exception as e:
            # Log the exception with traceback information
            logging.error("Failed to write to file: %s. Error: %s", self.filename, str(e), exc_info=True)
            return SFTPServer.convert_errno(errno.EIO)  # Input/Output Error


    def close(self):
        # No actual file to close in memory, but you might clear or reset the buffer if needed
        pass

    def stat(self):
        try:
            mode, _ = self.fs[self.filename]
            attr = SFTPAttributes()
            attr.st_mode = mode
            # Since BytesIO doesn't support file stats, return the stored mode
            return attr
        except KeyError:
            return SFTPServer.convert_errno(errno.ENOENT)

    def chattr(self, attr):
        try:
            if attr is not None:
                # Simulate changing attributes by updating the mode in the filesystem dictionary
                _, file_obj = self.fs[self.filename]
                self.fs[self.filename] = (attr.st_mode, file_obj)
                return SFTP_OK
        except KeyError:
            return SFTPServer.convert_errno(errno.ENOENT)


class InMemorySFTPServer(SFTPServerInterface):
    # Simulated in-memory file system
    ROOT = "/"
    def __init__(self, server):
        # Initialize root directory
        ims = InMemoryFileSystem()
        super().__init__(server)
        self
        self.fs = ims.fs

    def _realpath(self, path):
        # Simple path normalization ignoring symlinks for simplicity
        return os.path.normpath(path)

    def list_folder(self, path):
        path = self._realpath(path)
        try:
            items = []
            for name, (mode, _) in self.fs.items():
                if os.path.dirname(name) == path:
                    attr = SFTPAttributes()
                    attr.st_mode = mode
                    attr.filename = os.path.basename(name)
                    items.append(attr)
            return items
        except KeyError:
            return SFTPServer.convert_errno(errno.ENOENT)

    def stat(self, path):
        path = self._realpath(path)
        try:
            mode, _ = self.fs[path]
            return SFTPAttributes(st_mode=mode)
        except KeyError:
            return SFTPServer.convert_errno(errno.ENOENT)

    def lstat(self, path):
        return self.stat(path)  # In our simple FS, stat and lstat are the same

    def open(self, path, flags, attr):
        logging.debug(f"Attempting to open file: {path} with flags: {flags}")
        path = self._realpath(path)
        logging.debug(f"Resolved path: {path}")

        mode = getattr(attr, 'st_mode', S_IFREG | 0o666)
        file_exists = path in self.fs

        if flags & os.O_CREAT:
            if file_exists and flags & os.O_EXCL:
                logging.error(f"File already exists: {path}")
                return SFTPServer.convert_errno(errno.EEXIST)
            if not file_exists:
                logging.info(f"Creating new file at path: {path}")
                self.fs[path] = (mode, io.BytesIO())

        try:
            _, file_obj = self.fs[path]
        except KeyError:
            logging.error(f"File not found: {path}")
            return SFTPServer.convert_errno(errno.ENOENT)

        if flags & os.O_APPEND:
            file_obj.seek(0, os.SEEK_END)
        else:
            file_obj.seek(0)

        logging.info(f"File opened successfully: {path}")
        fobj = StubSFTPHandle(flags)
        fobj.filename = path
        fobj.readfile = file_obj
        fobj.writefile = file_obj
        return fobj

    def write(self, data):
        logging.debug(f"Attempting to write to file: {self.filename} with mode: {self.mode}")
        if 'w' in self.mode or 'a' in self.mode:
            self.file_obj.write(data)
            self.file_obj.flush()  # Ensure data is written
            logging.debug(f"Written {len(data)} bytes to file: {self.filename}")
            return len(data)
        else:
            logging.error("Write operation not allowed due to file mode restrictions")
            return SFTPServer.convert_errno(errno.EBADF)

    def remove(self, path):
        path = self._realpath(path)
        try:
            del self.fs[path]
            return SFTP_OK
        except KeyError:
            return SFTPServer.convert_errno(errno.ENOENT)

    def rename(self, oldpath, newpath):
        oldpath = self._realpath(oldpath)
        newpath = self._realpath(newpath)
        try:
            self.fs[newpath] = self.fs.pop(oldpath)
            return SFTP_OK
        except KeyError:
            return SFTPServer.convert_errno(errno.ENOENT)

    def mkdir(self, path, attr):
        path = self._realpath(path)
        mode = getattr(attr, 'st_mode', S_IFDIR | 0o755)
        if path in self.fs:
            return SFTPServer.convert_errno(errno.EEXIST)
        self.fs[path] = (mode, io.BytesIO())
        return SFTP_OK

    def rmdir(self, path):
        path = self._realpath(path)
        try:
            if not any(name.startswith(path + '/') for name in self.fs):
                del self.fs[path]
                return SFTP_OK
            else:
                return SFTPServer.convert_errno(errno.ENOTEMPTY)
        except KeyError:
            return SFTPServer.convert_errno(errno.ENOENT)

    def symlink(self, target_path, path):
        # Symlinks are stored as normal files with a special flag
        path = self._realpath(path)
        self.fs[path] = (S_IFREG | 0o777, io.BytesIO(target_path.encode()))
        return SFTP_OK

    def readlink(self, path):
        path = self._realpath(path)
        try:
            mode, file_obj = self.fs[path]
            file_obj.seek(0)
            return file_obj.read().decode()
        except KeyError:
            return SFTPServer.convert_errno(errno.ENOENT)


ssh_server = StubServer()