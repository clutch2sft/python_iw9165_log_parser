import asyncssh
import asyncio
import os
from asyncssh.sftp import SFTPAttrs, SFTPName
import stat as statmodule
import pwd, grp, time, stat
import fs.errors  # Import fs errors directly
from AsyncSFTPHandle import AsyncSFTPHandle

class AsyncSFTPServer(asyncssh.SFTPServer):
    def __init__(self, conn, fs, logger):

        self.conn = conn
        self.fs = fs
        self.custom_logger = logger
        # Set the root directory based on a username or another criterion
        username = conn.get_extra_info('username', 'default_user')
        root = f'/'  # Customize the path as needed
        #os.makedirs(root, exist_ok=True)
        super().__init__(conn, chroot=root)
        self.custom_logger.info(f'Initialized SFTP server with root: {root} for user: {username}')
    
    def session_ended(self):
        self.custom_logger.info('SFTP session ended.')
        super().session_ended()
    
    async def _realpath(self, path):
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._realpathsync, path)

    def _realpathsync(self, path):
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            real_path = self.fs.getsyspath(path) 
            self.custom_logger.debug(f"Resolved real path for {path}: {real_path}")
            return real_path
        except Exception as e:
            self.custom_logger.error(f"Failed to resolve path {path}: {str(e)}")
            raise

    async def list_folder(self, path):
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._list_folder_sync, path)

    def _list_folder_sync(self, path):
        out = []
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            files_listed = self.fs.listdir(path)
            self.custom_logger.debug(f"Listing folder at {path}, contents: {files_listed}")

            for fname in files_listed:
                full_path = os.path.join(path, fname)
                info = self.fs.getinfo(full_path, namespaces=['details'])
                attr = SFTPAttrs(size=info.get('details', 'size', 0),
                                uid=info.get('details', 'uid', 0),
                                gid=info.get('details', 'gid', 0),
                                permissions=info.get('details', 'permissions', 0o755),
                                atime=info.get('details', 'accessed', 0),
                                mtime=info.get('details', 'modified', 0))

                mode = stat.filemode(attr.permissions)
                user = pwd.getpwuid(attr.uid).pw_name
                group = grp.getgrgid(attr.gid).gr_name
                size = attr.size
                mtime = time.strftime('%b %d %H:%M', time.localtime(attr.mtime))
                longname = f'{mode} 1 {user} {group} {size} {mtime} {fname}'

                # Ensure SFTPName uses this longname
                entry = SFTPName(fname, longname, attr)
                out.append(entry)
        except OSError as e:
            self.custom_logger.error(f"Error listing folder {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))
        except Exception as e:
            self.custom_logger.error(f"Error listing folder {path}: {str(e)}")
            raise asyncssh.SFTPError(asyncssh.FX_FAILURE, 'Failed to list folder')
        return out

    def listdir(self, path):
        return self.list_folder(path)

    async def stat(self, path):
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._stat_sync, path)

    def _stat_sync(self, path):
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            info = self.fs.getinfo(path, namespaces=['details'])
            attrs = SFTPAttrs()
            attrs.size = info.get('details', 'size', 0)  # file size in bytes
            attrs.uid = info.get('details', 'uid', 0)  # default to '0' since UID/GID isn't tracked by MemoryFS
            attrs.gid = info.get('details', 'gid', 0)
            attrs.permissions = 0o755  # Default permissions (rwxr-xr-x)
            attrs.atime = info.get('details', 'accessed', None)  # access time as epoch
            attrs.mtime = info.get('details', 'modified', None)  # modification time as epoch

            # Set the file type based on the info from MemoryFS
            if self.fs.isdir(path):
                attrs.permissions |= statmodule.S_IFDIR
            else:
                attrs.permissions |= statmodule.S_IFREG

            self.custom_logger.debug(f"Getting details for {path}: {attrs}")
            return attrs
        except OSError as e:
            self.custom_logger.error(f"Error listing folder {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))
        except Exception as e:
            self.custom_logger.error(f"Error listing folder {path}: {str(e)}")
            raise asyncssh.SFTPError(asyncssh.FX_FAILURE, 'Failed to list folder')

    def lstat(self, path):
        return self.stat(path)  # In MemoryFS, stat and lstat are equivalent
    # Additional methods follow the same pattern: Define async wrapper and synchronous function

    async def open(self, path, pflags, attrs):
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        self.custom_logger.debug(f"Opening file: {path} with flags {pflags}")
        return await asyncio.get_event_loop().run_in_executor(None, self._open_sync, path, pflags, attrs)

    def _open_sync(self, path, pflags, attrs):
        self.custom_logger.debug(f"open_sync for {path} with flags {pflags} (binary: {bin(pflags)})")

        # Determine file mode based on flags
        if pflags & os.O_APPEND:
            mode = 'ab' if pflags & os.O_WRONLY else 'a+b'
        elif pflags & os.O_WRONLY:
            mode = 'wb'  # Open for writing only
        elif pflags & os.O_RDWR:
            mode = 'w+b'  # Open for reading and writing
        else:
            mode = 'rb'  # Default to read only

        # Adjust for creation flag
        mode += '+' if pflags & os.O_CREAT and '+' not in mode else ''

        try:
            f = self.fs.open(path, mode)
            self.custom_logger.debug(f"Opened file {path} with mode {mode}")
            return AsyncSFTPHandle(f, self.fs, path, self.custom_logger)
        except fs.errors.ResourceNotFound:
            if 'w' in mode:
                self.fs.touch(path)
                f = self.fs.open(path, mode)
                self.custom_logger.debug(f"Created and opened file {path} with mode {mode}")
                return AsyncSFTPHandle(f, self.fs, path, self.custom_logger)
            else:
                self.custom_logger.error(f"File not found and not allowed to create: {path}")
                raise asyncssh.SFTPError(asyncssh.FX_NO_SUCH_FILE, f"File not found: {path}")
        except Exception as e:
            self.custom_logger.error(f"Failed to open file {path}: {str(e)}")
            raise asyncssh.SFTPError(asyncssh.FX_FAILURE, f"Error opening file: {path}")


    async def remove(self, path):
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._remove, path)

    def _remove(self, path):
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            self.fs.remove(path)
            self.custom_logger.info(f"Removed file {path}")
        except OSError as e:
            self.custom_logger.error(f"Failed to open file {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def rename(self, oldpath, newpath):
        oldpath = oldpath.decode('utf-8') if isinstance(oldpath, bytes) else oldpath
        newpath = newpath.decode('utf-8') if isinstance(newpath, bytes) else newpath
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if oldpath.startswith('/'):
            oldpath = oldpath[1:]  # Remove leading slash for MemoryFS compatibility
        if newpath.startswith('/'):
            newpath = newpath[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._rename, oldpath, newpath)

    def _rename(self, oldpath, newpath):
        try:
            oldpath = oldpath.decode('utf-8') if isinstance(oldpath, bytes) else oldpath
            newpath = newpath.decode('utf-8') if isinstance(newpath, bytes) else newpath
            self.fs.move(oldpath, newpath)
            self.custom_logger.info(f"Renamed from {oldpath} to {newpath}")
        except OSError as e:
            self.custom_logger.error(f"Failed to open find {oldpath} for renaming: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def mkdir(self, path, attr):
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._mkdir, path, attr)

    def _mkdir(self, path, attr):
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            self.fs.makedir(path)
            self.custom_logger.info(f"Directory created at {path}")
            if attr is not None:
                # Set file attributes if provided
                # Assuming attr includes permissions
                permissions = getattr(attr, 'st_mode', 0o755)
                self.fs.setinfo(path, {'details': {'permissions': permissions}})
        except OSError as e:
            self.custom_logger.error(f"Failed to create directory {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def rmdir(self, path):
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._rmdir, path)

    def _rmdir(self, path):
        try:
            path = path.decode('utf-8')  if isinstance(path, bytes) else path
            self.fs.removedir(path)
            self.custom_logger.info(f"Directory removed at {path}")
        except OSError as e:
            self.custom_logger.error(f"Failed to remove directory {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def chattr(self, path, attr):
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._chattr, path, attr)

    def _chattr(self, path, attr):
        try:
            # Assuming attr includes permissions and potentially other metadata
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            permissions = getattr(attr, 'st_mode', None)
            if permissions:
                self.fs.setinfo(path, {'details': {'permissions': permissions}})
            self.custom_logger.info(f"Changed attributes for {path}: {attr}")
        except OSError as e:
            self.custom_logger.error(f"Failed to change attributes for {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def readlink(self, path):
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._readlink, path)

    def _readlink(self, path):
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            symlink_target = self.fs.readlink(path)
            self.custom_logger.info(f"Read symlink at {path}, target is {symlink_target}")
            return symlink_target
        except OSError as e:
            self.custom_logger.error(f"Failed to read symlink {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def symlink(self, target_path, path):
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._symlink, target_path, path)

    def _symlink(self, target_path, path):
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            self.fs.symlink(target_path, path)
            self.custom_logger.info(f"Created symlink at {path} pointing to {target_path}")
        except OSError as e:
            self.custom_logger.error(f"Failed to create symlink from {path} to {target_path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    @staticmethod
    def convert_errno(errno):
        if errno == os.errno.ENOENT:
            return asyncssh.FX_NO_SUCH_FILE
        elif errno == os.errno.EACCES:
            return asyncssh.FX_PERMISSION_DENIED
        elif errno == os.errno.ENOTDIR:
            return asyncssh.FX_NO_SUCH_PATH
        # Add other mappings as necessary
        return asyncssh.FX_FAILURE  # Default failure code


# async def start_server(logger):
#     fs = MemoryFS()  # Initialize filesystem here if not passed externally
#     sftp_server = AsyncSFTPServer(None, None, fs, logger)
#     await sftp_server.start_sftp_server()

# if __name__ == "__main__":
#     import logging
#     logging.basicConfig(level=logging.DEBUG)
#     logger = logging.getLogger()

#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(start_server(logger))
