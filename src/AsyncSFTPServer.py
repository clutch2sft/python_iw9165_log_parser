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
        self.cwd = root
        super().__init__(conn, chroot=root)
        self.custom_logger.info(f'{self.__class__.__name__}: Initialized SFTP server with root: {root} for user: {username}')
    
    def session_ended(self):
        method_name = self.session_ended.__name__
        self.custom_logger.info(f'{self.__class__.__name__}:{method_name} SFTP session ended.')
        super().session_ended()

    def get_cwd(self):
        method_name = self.get_cwd.__name__
        if hasattr(self, 'cwd') and self.cwd:
            return self.cwd
        else:
            # Fallback to a default directory or log an error
            self.logger.error(f"{self.__class__.__name__}:{method_name} Current working directory not set. Falling back to root.")
            return "/"  # or handle it by setting a new default cwd

    def _normalize_path(self, path):
        method_name = self._normalize_path.__name__
        # Convert path to a correct format by stripping leading slashes
        if path.startswith('/'):
            path = path.lstrip('/')  # Remove leading slashes for compatibility
        # Handle navigation to parent directory
        if path == '..':
            self.cwd = os.path.dirname(self.cwd)
            return self.cwd
        elif path in ('.', ''):
            return self.cwd  # Stay in the current directory
        else:
            # Construct the new path based on current directory
            new_path = os.path.join(self.cwd, path)
            # Normalize the path to handle any '..' or similar components
            normalized_path = os.path.normpath(new_path)
            return normalized_path

    async def change_directory(self, path):
        method_name = self.change_directory.__name__
        normalized_path = self._normalize_path(path)
        if self.fs.isdir(normalized_path):
            self.cwd = normalized_path  # Safe as cwd is always initialized
            self.logger.info(f"{self.__class__.__name__}:{method_name} Changed directory to {self.cwd}")
        else:
            raise FileNotFoundError(f"{self.__class__.__name__}:{method_name} Directory not found: {path}")

    # Overwrite the SFTPServer method to handle path correctly
    async def realpath(self, path):
        method_name = self.realpath.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        return self._normalize_path(path)

    async def _realpath(self, path):
        method_name = self._realpath.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._realpathsync, path)

    def _realpathsync(self, path):
        try:
            method_name = self._realpathsync.__name__
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            # Ensure path is correctly interpreted relative to the root of MemoryFS
            if path.startswith('/'):
                path = path[1:]  # Remove leading slash for MemoryFS compatibility
            real_path = self.fs.getsyspath(path) 
            self.custom_logger.debug(f"{self.__class__.__name__}:{method_name} Resolved real path for {path}: {real_path}")
            return real_path
        except Exception as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Failed to resolve path {path}: {str(e)}")
            raise

    async def list_folder(self, path):
        method_name = self.list_folder.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._list_folder_sync, path)

    def _list_folder_sync(self, path):
        method_name = self._list_folder_sync.__name__
        out = []
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            files_listed = self.fs.listdir(path)
            self.custom_logger.debug(f"{self.__class__.__name__}:{method_name} Listing folder at {path}, contents: {files_listed}")

            for fname in files_listed:
                full_path = os.path.join(path, fname)
                info = self.fs.getinfo(full_path, namespaces=['details', 'stat'])

                # Use 'stat' namespace for uid, gid, and permissions if 'details' doesn't provide them
                attr = SFTPAttrs(size=info.get('details', 'size', 0),
                                uid=info.get('stat', 'uid', 0),
                                gid=info.get('stat', 'gid', 0),
                                permissions=info.get('stat', 'permissions', 0o755),
                                atime=info.get('details', 'accessed', 0),
                                mtime=info.get('details', 'modified', 0))

                mode = stat.filemode(attr.permissions)
                user = pwd.getpwuid(attr.uid).pw_name
                group = grp.getgrgid(attr.gid).gr_name
                size = attr.size
                mtime = time.strftime('%b %d %H:%M', time.localtime(attr.mtime))
                
                self.custom_logger.debug(f"{self.__class__.__name__}:{method_name} Setting permissions for {'directory' if info.is_dir else 'file'} '{fname}' to {oct(attr.permissions)} with mode {mode}")

                # Include directory or regular file indication in permissions
                if info.is_dir:
                    attr.permissions |= stat.S_IFDIR
                    mode = 'd' + mode[1:]  # Adjust mode string for directories
                else:
                    attr.permissions |= stat.S_IFREG
                    mode = '-' + mode[1:]  # Adjust mode string for files

                self.custom_logger.debug(f"{self.__class__.__name__}:{method_name} Finished setting permissions for {'directory' if info.is_dir else 'file'} '{fname}' to {oct(attr.permissions)} with mode {mode}")

                longname = f'{mode} 1 {user} {group} {size} {mtime} {fname}'

                # Ensure SFTPName uses this longname
                entry = SFTPName(fname, longname, attr)
                out.append(entry)
        except OSError as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Error listing folder {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))
        except Exception as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Error listing folder {path}: {str(e)}")
            raise asyncssh.SFTPError(asyncssh.FX_FAILURE, 'Failed to list folder')
        return out

    def listdir(self, path):
        method_name = self.listdir.__name__
        return self.list_folder(path)

    async def stat(self, path):
        method_name = self.stat.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._stat_sync, path)

    def _stat_sync(self, path):
        method_name = self._stat_sync.__name__
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            fname = os.path.basename(path)
            info = self.fs.getinfo(path, namespaces=['details', 'stat'])

            # Use 'stat' namespace for uid, gid, and permissions if 'details' doesn't provide them
            attr = SFTPAttrs(size=info.get('details', 'size', 0),
                            uid=info.get('stat', 'uid', 0),
                            gid=info.get('stat', 'gid', 0),
                            permissions=info.get('stat', 'permissions', 0o755),
                            atime=info.get('details', 'accessed', 0),
                            mtime=info.get('details', 'modified', 0))

            mode = stat.filemode(attr.permissions)
            user = pwd.getpwuid(attr.uid).pw_name
            group = grp.getgrgid(attr.gid).gr_name
            size = attr.size
            mtime = time.strftime('%b %d %H:%M', time.localtime(attr.mtime))
            longname = f'{mode} 1 {user} {group} {size} {mtime} {fname}'

            # Include directory or regular file indication in permissions
            if info.is_dir:
                attr.permissions |= stat.S_IFDIR
                mode = 'd' + mode[1:]  # Adjust mode string for directories
            else:
                attr.permissions |= stat.S_IFREG

            self.custom_logger.debug(f"{self.__class__.__name__}:{method_name} Getting details for {path}: {attr}")
            return attr
        except OSError as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Error listing folder {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))
        except Exception as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Error listing folder {path}: {str(e)}")
            raise asyncssh.SFTPError(asyncssh.FX_FAILURE, 'Failed to list folder')

    def lstat(self, path):
        return self.stat(path)  # In MemoryFS, stat and lstat are equivalent
    # Additional methods follow the same pattern: Define async wrapper and synchronous function

    async def open(self, path, pflags, attrs):
        method_name = self.open.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        self.custom_logger.debug(f"{self.__class__.__name__}:{method_name} Opening file: {path} with flags {pflags}")
        return await asyncio.get_event_loop().run_in_executor(None, self._open_sync, path, pflags, attrs)

    def _open_sync(self, path, pflags, attrs):
        method_name = self._open_sync.__name__
        self.custom_logger.debug(f"{self.__class__.__name__}:{method_name} open_sync for {path} with flags {pflags} (binary: {bin(pflags)})")

        if pflags & 0x02:  # SSH_FXF_WRITE
            mode = 'wb'
            if pflags & 0x01:  # SSH_FXF_READ
                mode += '+'
        elif pflags & 0x01:  # SSH_FXF_READ
            mode = 'rb'
        else:
            mode = 'rb'  # Default to read only

        if pflags & 0x04:  # SSH_FXF_APPEND
            mode = 'ab' if 'r' not in mode else 'a+b'

        # # Determine file mode based on flags
        # if pflags & os.O_APPEND:
        #     mode = 'ab' if pflags & os.O_WRONLY else 'a+b'
        # elif pflags & os.O_WRONLY:
        #     mode = 'wb'  # Open for writing only
        # elif pflags & os.O_RDWR:
        #     mode = 'w+b'  # Open for reading and writing
        # else:
        #     mode = 'rb'  # Default to read only
            
        self.custom_logger.debug(f"{self.__class__.__name__}:{method_name} Opened file {path} with mode {mode}")
        # Adjust for creation flag
        mode += '+' if pflags & os.O_CREAT and '+' not in mode else ''

        try:
            f = self.fs.open(path, mode)
            self.custom_logger.debug(f"{self.__class__.__name__}:{method_name} Opened file {path} with mode {mode}")
            return AsyncSFTPHandle(f, self.fs, path, self.custom_logger)
        except fs.errors.ResourceNotFound:
            if 'w' in mode:
                self.fs.touch(path)
                f = self.fs.open(path, mode)
                self.custom_logger.debug(f"{self.__class__.__name__}:{method_name} Created and opened file {path} with mode {mode}")
                return AsyncSFTPHandle(f, self.fs, path, self.custom_logger)
            else:
                self.custom_logger.error(f"{self.__class__.__name__}:{method_name} File not found and not allowed to create: {path}")
                raise asyncssh.SFTPError(asyncssh.FX_NO_SUCH_FILE, f"File not found: {path}")
        except Exception as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Failed to open file {path}: {str(e)}")
            raise asyncssh.SFTPError(asyncssh.FX_FAILURE, f"Error opening file: {path}")


    async def remove(self, path):
        method_name = self.remove.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._remove, path)

    def _remove(self, path):
        method_name = self._remove.__name__
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            self.fs.remove(path)
            self.custom_logger.info(f"{self.__class__.__name__}:{method_name} Removed file {path}")
        except OSError as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Failed to open file {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def rename(self, oldpath, newpath):
        method_name = self.rename.__name__
        oldpath = oldpath.decode('utf-8') if isinstance(oldpath, bytes) else oldpath
        newpath = newpath.decode('utf-8') if isinstance(newpath, bytes) else newpath
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if oldpath.startswith('/'):
            oldpath = oldpath[1:]  # Remove leading slash for MemoryFS compatibility
        if newpath.startswith('/'):
            newpath = newpath[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._rename, oldpath, newpath)

    def _rename(self, oldpath, newpath):
        method_name = self._rename.__name__
        try:
            oldpath = oldpath.decode('utf-8') if isinstance(oldpath, bytes) else oldpath
            newpath = newpath.decode('utf-8') if isinstance(newpath, bytes) else newpath
            self.fs.move(oldpath, newpath)
            self.custom_logger.info(f"{self.__class__.__name__}:{method_name} Renamed from {oldpath} to {newpath}")
        except OSError as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Failed to open find {oldpath} for renaming: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def mkdir(self, path, attr):
        method_name = self.mkdir.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._mkdir, path, attr)

    def _mkdir(self, path, attr):
        method_name = self._mkdir.__name__
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            self.fs.makedir(path)
            self.custom_logger.info(f"{self.__class__.__name__}:{method_name} Directory created at {path}")
            if attr is not None:
                # Set file attributes if provided
                # Assuming attr includes permissions
                permissions = getattr(attr, 'st_mode', 0o755)
                self.fs.setinfo(path, {'details': {'permissions': permissions}})
        except OSError as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Failed to create directory {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def rmdir(self, path):
        method_name = self.rmdir.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._rmdir, path)

    def _rmdir(self, path):
        method_name = self._rmdir.__name__
        try:
            path = path.decode('utf-8')  if isinstance(path, bytes) else path
            self.fs.removedir(path)
            self.custom_logger.info(f"{self.__class__.__name__}:{method_name} Directory removed at {path}")
        except OSError as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Failed to remove directory {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def chattr(self, path, attr):
        method_name = self.chattr.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._chattr, path, attr)

    def _chattr(self, path, attr):
        method_name = self._chattr.__name__
        try:
            # Assuming attr includes permissions and potentially other metadata
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            permissions = getattr(attr, 'st_mode', None)
            if permissions:
                self.fs.setinfo(path, {'details': {'permissions': permissions}})
            self.custom_logger.info(f"{self.__class__.__name__}:{method_name} Changed attributes for {path}: {attr}")
        except OSError as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Failed to change attributes for {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def readlink(self, path):
        method_name = self.readlink.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._readlink, path)

    def _readlink(self, path):
        method_name = self._readlink.__name__
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            symlink_target = self.fs.readlink(path)
            self.custom_logger.info(f"{self.__class__.__name__}:{method_name} Read symlink at {path}, target is {symlink_target}")
            return symlink_target
        except OSError as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Failed to read symlink {path}: {str(e)}")
            raise asyncssh.SFTPError(AsyncSFTPServer.convert_errno(e.errno), str(e))

    async def symlink(self, target_path, path):
        method_name = self.symlink.__name__
        path = path.decode('utf-8') if isinstance(path, bytes) else path
        # Ensure path is correctly interpreted relative to the root of MemoryFS
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash for MemoryFS compatibility
        return await asyncio.get_event_loop().run_in_executor(None, self._symlink, target_path, path)

    def _symlink(self, target_path, path):
        method_name = self._symlink.__name__
        try:
            path = path.decode('utf-8') if isinstance(path, bytes) else path
            self.fs.symlink(target_path, path)
            self.custom_logger.info(f"{self.__class__.__name__}:{method_name} Created symlink at {path} pointing to {target_path}")
        except OSError as e:
            self.custom_logger.error(f"{self.__class__.__name__}:{method_name} Failed to create symlink from {path} to {target_path}: {str(e)}")
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
