import os
import stat as statmodule
from paramiko import SFTPServerInterface, SFTPAttributes, SFTPServer, SFTPHandle, SFTP_OK
from stub_sftp_handle import StubSFTPHandle
from fs.errors import ResourceNotFound




class StubSFTPServer(SFTPServerInterface):
    def __init__(self, channel, name, server, srv_fs, logger, *args, **kwargs):
        super().__init__(server)
        self.fs = srv_fs
        self.logger = logger
        # - setup paramiko logging


    def _realpath(self, path):
        try:
            real_path = self.fs.getsyspath(path)
            self.logger.debug(f"Resolved real path for {path}: {real_path}")
            return real_path
        except Exception as e:
            self.logger.error(f"Failed to resolve path {path}: {str(e)}")
            raise

    def list_folder(self, path):
        try:
            out = []
            files_listed = self.fs.listdir(path)
            self.logger.debug(f"Listing folder at {path}, contents: {files_listed}")
            for fname in files_listed:
                full_path = os.path.join(path, fname)  # Use os.path.join to ensure proper path handling
                info = self.fs.getinfo(full_path, namespaces=['details', 'stat'])
                attr = SFTPAttributes()
                attr.filename = fname
                attr.st_size = info.get('details', 'size', 0)
                attr.st_uid = info.get('details', 'uid', 0)
                attr.st_gid = info.get('details', 'gid', 0)
                attr.st_mode = info.get('details', 'permissions', 0o755)
                attr.permissions = 0o755  # Default permissions (rwxr-xr-x)
                attr.st_atime = info.get('details', 'accessed', None)
                attr.st_mtime = info.get('details', 'modified', None)
                attr._flags = (SFTPAttributes.FLAG_SIZE | SFTPAttributes.FLAG_UIDGID |
                   SFTPAttributes.FLAG_PERMISSIONS | SFTPAttributes.FLAG_AMTIME)
                # Set the file type based on the info from MemoryFS
                if info.is_dir:
                    attr.st_mode = statmodule.S_IFDIR | attr.permissions  # Directory flag
                else:
                    attr.st_mode = statmodule.S_IFREG | attr.permissions  # Regular file flag

                if 'stat' in info.namespaces:  # Check if 'stat' namespace is actually fetched
                    stat_info = info.raw['stat']
                    attr.update_from_stat(stat_info)  # Update attributes from stat info if available

                for key, value in vars(attr).items():
                    self.logger.debug(f"{key}: {value}")

                out.append(attr)
            return out
        except Exception as e:
            self.logger.error(f"Error listing folder {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)
        
    def listdir(self, path):
        return self.list_folder(path)

    def stat(self, path):
        try:
            info = self.fs.getinfo(path, namespaces=['details'])
            attrs = SFTPAttributes()
            attrs.size = info.get('details', 'size', 0)  # file size in bytes
            attrs.uid = info.get('details', 'uid', 0)  # default to '0' since UID/GID isn't tracked by MemoryFS
            attrs.gid = info.get('details', 'gid', 0)
            attrs.permissions = 0o755  # Default permissions (rwxr-xr-x)
            attrs.atime = info.get('details', 'accessed', None)  # access time as epoch
            attrs.mtime = info.get('details', 'modified', None)  # modification time as epoch
            attrs._flags = (SFTPAttributes.FLAG_SIZE | SFTPAttributes.FLAG_UIDGID |
                SFTPAttributes.FLAG_PERMISSIONS | SFTPAttributes.FLAG_AMTIME)
            # Set the file type based on the info from MemoryFS
            if info.is_dir:
                attrs.st_mode = statmodule.S_IFDIR | attrs.permissions  # Directory flag
            else:
                attrs.st_mode = statmodule.S_IFREG | attrs.permissions  # Regular file flag

            self.logger.debug(f"Getting details for {path}: {attrs}")
            return attrs
        except OSError as e:
            self.logger.error(f"Failed to get details for {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)


    def lstat(self, path):
        return self.stat(path)  # In MemoryFS, stat and lstat are equivalent

    def open(self, path, flags, attr):
        # Determine the mode based on the flags
        mode = 'r+b'  # Default mode for both reading and writing, in binary mode
        if flags & os.O_WRONLY:
            if flags & os.O_APPEND:
                mode = 'ab'  # Append in binary mode
            else:
                mode = 'wb'  # Write in binary mode
        elif flags & os.O_RDWR:
            if flags & os.O_APPEND:
                mode = 'a+b'  # Read/append in binary mode
            else:
                mode = 'w+b'  # Read/write in binary mode
        else:
            mode = 'rb'  # Default to read-only in binary mode if no flags are set

        try:
            f = self.fs.open(path, mode)
            self.logger.debug(f"Opened file {path} with mode {mode}")
            fobj = StubSFTPHandle(f, path, self.logger)
            fobj.filename = path
            fobj.readfile = f
            fobj.writefile = f
            return fobj
        except OSError as e:
            self.logger.error(f"Failed to open file {path} with mode {mode}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def remove(self, path):
        try:
            self.fs.remove(path)
            self.logger.info(f"Removed file {path}")
            return SFTP_OK
        except OSError as e:
            self.logger.error(f"Failed to remove file {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def rename(self, oldpath, newpath):
        try:
            self.fs.move(oldpath, newpath)
            self.logger.info(f"Renamed from {oldpath} to {newpath}")
            return SFTP_OK
        except ResourceNotFound:
            self.logger.error(f"Failed to find {oldpath} for renaming")
            return SFTPServer.convert_errno(os.errno.ENOENT)
        except OSError as e:
            self.logger.error(f"Error renaming from {oldpath} to {newpath}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def mkdir(self, path, attr):
        try:
            self.fs.makedir(path)
            self.logger.info(f"Directory created at {path}")
            if attr is not None:
                # Set file attributes if provided
                # Assuming attr includes permissions
                permissions = getattr(attr, 'st_mode', 0o755)
                self.fs.setinfo(path, {'details': {'permissions': permissions}})
            return SFTP_OK
        except OSError as e:
            self.logger.error(f"Failed to create directory {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def rmdir(self, path):
        try:
            self.fs.removedir(path)
            self.logger.info(f"Directory removed at {path}")
            return SFTP_OK
        except ResourceNotFound:
            self.logger.error(f"Directory not found: {path}")
            return SFTPServer.convert_errno(os.errno.ENOENT)
        except OSError as e:
            self.logger.error(f"Failed to remove directory {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)
        
    def chattr(self, path, attr):
        try:
            # Assuming attr includes permissions and potentially other metadata
            permissions = getattr(attr, 'st_mode', None)
            if permissions:
                self.fs.setinfo(path, {'details': {'permissions': permissions}})
            self.logger.info(f"Changed attributes for {path}: {attr}")
            return SFTP_OK
        except ResourceNotFound:
            self.logger.error(f"File not found for changing attributes: {path}")
            return SFTPServer.convert_errno(os.errno.ENOENT)
        except OSError as e:
            self.logger.error(f"Failed to change attributes for {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def readlink(self, path):
        try:
            symlink_target = self.fs.readlink(path)
            self.logger.info(f"Read symlink at {path}, target is {symlink_target}")
            return symlink_target
        except ResourceNotFound:
            self.logger.error(f"Symlink not found: {path}")
            return SFTPServer.convert_errno(os.errno.ENOENT)
        except OSError as e:
            self.logger.error(f"Failed to read symlink {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def symlink(self, target_path, path):
        try:
            self.fs.symlink(target_path, path)
            self.logger.info(f"Created symlink at {path} pointing to {target_path}")
            return SFTP_OK
        except ResourceNotFound:
            self.logger.error(f"Failed to create symlink due to missing target: {target_path}")
            return SFTPServer.convert_errno(os.errno.ENOENT)
        except OSError as e:
            self.logger.error(f"Failed to create symlink from {path} to {target_path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)
