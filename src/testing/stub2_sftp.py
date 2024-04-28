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

import os, errno, io, logging
from paramiko import ServerInterface, SFTPServerInterface, SFTPServer, SFTPAttributes, \
    SFTPHandle, SFTP_OK, AUTH_SUCCESSFUL, OPEN_SUCCEEDED
from InMemoryFileSystem import InMemoryFileSystem

class InMemorySFTPHandle(SFTPHandle):
    def __init__(self, file_obj):
        super(InMemorySFTPHandle, self).__init__()
        self.file_obj = file_obj
        self.logger = logging.getLogger('InMemorySFTPHandle')

    def _realpath(self, path):
        # Simulates the resolution of a real path, adjusting for root and other factors.
        return path


    def read(self, offset, length):
        try:
            self.file_obj.seek(offset)
            data = self.file_obj.read(length)
            self.logger.debug(f"Read {len(data)} bytes from offset {offset}")
            return data
        except Exception as e:
            self.logger.error(f"Failed to read from file: {e}")
            raise IOError("Failed to read from file") from e

    def write(self, offset, data):
        try:
            self.file_obj.seek(offset)
            self.file_obj.write(data)
            self.logger.debug(f"Wrote {len(data)} bytes to offset {offset}")
            return len(data)
        except Exception as e:
            self.logger.error(f"Failed to write to file: {e}")
            raise IOError("Failed to write to file") from e

    def close(self):
        try:
            # If you have any cleanup logic or need to update metadata, add it here
            self.logger.debug("Closing file handle")
        except Exception as e:
            self.logger.error(f"Failed to close file handle: {e}")
            raise IOError("Failed to close file handle") from e
        finally:
            super().close()  # It's good practice to call the super class's close method if it does any additional work.

    def stat(self):
        try:
            # Implement stat if needed to return file metadata
            # You would need to simulate file attributes typically expected by SFTP clients
            raise NotImplementedError("stat method not implemented.")
        except Exception as e:
            self.logger.error(f"Error obtaining file statistics: {e}")
            raise IOError("Error obtaining file statistics") from e

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


class StubSFTPHandle (SFTPHandle):
    def stat(self):
        try:
            return SFTPAttributes.from_stat(os.fstat(self.readfile.fileno()))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def chattr(self, attr):
        # python doesn't have equivalents to fchown or fchmod, so we have to
        # use the stored filename
        try:
            SFTPServer.set_file_attr(self.filename, attr)
            return SFTP_OK
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)


class StubSFTPServer (SFTPServerInterface):
    # assume current folder is a fine root
    # (the tests always create and eventualy delete a subfolder, so there shouldn't be any mess)
    KEY = None
    ROOT = '/'
    def __init__(self, flags):
        self.fs = InMemoryFileSystem()
        self.ROOT = '/'


    def _realpath(self, path):
        return os.path.join(self.ROOT, path.lstrip('/'))


    # def listdir(self, path):
    #     real_path = self._realpath(path)
    #     try:
    #         contents = self.fs.list_directory(real_path)  # Assuming this method returns list of file names
    #         out = []
    #         for fname in contents:
    #             attr = self.fs.stat(os.path.join(real_path, fname))  # Make sure this method returns SFTPAttributes
    #             out.append(attr)
    #         return out
    #     except KeyError:
    #         self.logger.error(f"Directory not found: {path}")
    #         raise IOError("No such file or directory")

    def list_folder(self, path):
        real_path = self._realpath(path)
        try:
            contents = self.fs.list_directory(real_path)  # Assuming this method returns list of file names
            out = []
            for fname in contents:
                attr = self.fs.stat(os.path.join(real_path, fname))  # Make sure this method returns SFTPAttributes
                out.append(attr)
            return out
        except KeyError:
            self.logger.error(f"Directory not found: {path}")
            raise IOError("No such file or directory")

    def stat(self, path):
        path = self._realpath(path)
        try:
            return SFTPAttributes.from_stat(os.stat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def lstat(self, path):
        path = self._realpath(path)
        try:
            return SFTPAttributes.from_stat(os.lstat(path))
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def open(self, path, flags, attr=None):
        real_path = self._realpath(path)
        if flags & os.O_CREAT:
            self.fs[real_path] = (0o100666, io.BytesIO())  # Use dictionary-like assignment

        if real_path not in self.fs:
            raise IOError(errno.ENOENT, os.strerror(errno.ENOENT), path)

        file_obj = self.fs[real_path][1]
        handle = InMemorySFTPHandle(file_obj)
        fobj = handle
        fobj.filename = self.fs[real_path]
        fobj.readfile = file_obj
        fobj.writefile = file_obj
        return fobj

    def remove(self, path):
        path = self._realpath(path)
        try:
            os.remove(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def rename(self, oldpath, newpath):
        oldpath = self._realpath(oldpath)
        newpath = self._realpath(newpath)
        try:
            self.fs.rename(oldpath, newpath)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def mkdir(self, path, attr):
        path = self._realpath(path)
        try:
            self.fs.mkdir(path)
            if attr is not None:
                SFTPServer.set_file_attr(path, attr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def rmdir(self, path):
        path = self._realpath(path)
        try:
            self.fs.rmdir(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def chattr(self, path, attr):
        path = self._realpath(path)
        try:
            SFTPServer.set_file_attr(path, attr)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def symlink(self, target_path, path):
        path = self._realpath(path)
        if (len(target_path) > 0) and (target_path[0] == '/'):
            # absolute symlink
            target_path = os.path.join(self.ROOT, target_path[1:])
            if target_path[:2] == '//':
                # bug in os.path.join
                target_path = target_path[1:]
        else:
            # compute relative to path
            abspath = os.path.join(os.path.dirname(path), target_path)
            if abspath[:len(self.ROOT)] != self.ROOT:
                # this symlink isn't going to work anyway -- just break it immediately
                target_path = '<error>'
        try:
            os.symlink(target_path, path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        return SFTP_OK

    def readlink(self, path):
        path = self._realpath(path)
        try:
            symlink = os.readlink(path)
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        # if it's absolute, remove the root
        if os.path.isabs(symlink):
            if symlink[:len(self.ROOT)] == self.ROOT:
                symlink = symlink[len(self.ROOT):]
                if (len(symlink) == 0) or (symlink[0] != '/'):
                    symlink = '/' + symlink
            else:
                symlink = '<error>'
        return symlink


ssh_server = StubServer()