import os, logging
from paramiko import ServerInterface, SFTPServerInterface, SFTPServer, SFTPAttributes, \
    SFTPHandle, SFTP_OK, AUTH_SUCCESSFUL, OPEN_SUCCEEDED
from fs.errors import ResourceNotFound

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
    def __init__(self, fs, path):
        super().__init__()
        self.fs = fs
        self.path = path

    def stat(self):
        try:
            info = self.fs.getinfo(self.path, namespaces=['stat'])
            return SFTPAttributes.from_stat(info.raw['stat'])
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)

    def chattr(self, attr):
        try:
            # Adapt this based on what attributes are being changed, example for permissions:
            permissions = getattr(attr, 'st_mode', None)
            if permissions:
                self.fs.setinfo(self.path, {'details': {'permissions': permissions}})
            return SFTP_OK
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)


class StubSFTPServer(SFTPServerInterface):

    KEY = None
    ROOT = '/virtual_root'
class StubSFTPServer(SFTPServerInterface):
    def __init__(self, channel, name, server, srv_fs, *args, **kwargs):
        super().__init__(server)  # Pass the server to the base class
        self.fs = srv_fs  # Assign the shared MemoryFS instance
        self.ROOT = '/'  # Set the root directory

    
    def _realpath(self, path):
        try:
            real_path = self.fs.getsyspath(path)
            logging.debug(f"Resolved real path for {path}: {real_path}")
            return real_path
        except Exception as e:
            logging.error(f"Failed to resolve path {path}: {str(e)}")
            raise

    def list_folder(self, path):
        try:
            out = []
            files_listed = self.fs.listdir(path)
            logging.debug(f"Listing folder at {path}, contents: {files_listed}")
            for fname in files_listed:
                full_path = os.path.join(path, fname)  # Use os.path.join to ensure proper path handling
                info = self.fs.getinfo(full_path, namespaces=['details', 'stat'])
                attr = SFTPAttributes()
                attr.filename = fname
                attr.st_size = info.get('details', 'size', 0)
                attr.st_uid = info.get('details', 'uid', 0)
                attr.st_gid = info.get('details', 'gid', 0)
                attr.st_mode = info.get('details', 'permissions', 0o755)
                attr.st_atime = info.get('details', 'accessed', None)
                attr.st_mtime = info.get('details', 'modified', None)
                attr._flags = (SFTPAttributes.FLAG_SIZE | SFTPAttributes.FLAG_UIDGID |
                   SFTPAttributes.FLAG_PERMISSIONS | SFTPAttributes.FLAG_AMTIME)

                if 'stat' in info.namespaces:  # Check if 'stat' namespace is actually fetched
                    stat_info = info.raw['stat']
                    attr.update_from_stat(stat_info)  # Update attributes from stat info if available

                for key, value in vars(attr).items():
                    logging.debug(f"{key}: {value}")

                out.append(attr)
            return out
        except Exception as e:
            logging.error(f"Error listing folder {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)
        
    def listdir(self, path):
        return self.list_folder(path)

    def stat(self, path):
        try:
            info = self.fs.getinfo(path, namespaces=['stat'])
            logging.debug(f"Getting stat for {path}: {info.raw['stat']}")
            return SFTPAttributes.from_stat(info.raw['stat'])
        except OSError as e:
            logging.error(f"Failed to get stat for {path}: {str(e)}")
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
            logging.debug(f"Opened file {path} with mode {mode}")
            fobj = SFTPHandle()
            fobj.filename = path
            fobj.readfile = f
            fobj.writefile = f
            return fobj
        except OSError as e:
            logging.error(f"Failed to open file {path} with mode {mode}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def remove(self, path):
        try:
            self.fs.remove(path)
            logging.info(f"Removed file {path}")
            return SFTP_OK
        except OSError as e:
            logging.error(f"Failed to remove file {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def rename(self, oldpath, newpath):
        try:
            self.fs.move(oldpath, newpath)
            logging.info(f"Renamed from {oldpath} to {newpath}")
            return SFTP_OK
        except ResourceNotFound:
            logging.error(f"Failed to find {oldpath} for renaming")
            return SFTPServer.convert_errno(os.errno.ENOENT)
        except OSError as e:
            logging.error(f"Error renaming from {oldpath} to {newpath}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def mkdir(self, path, attr):
        try:
            self.fs.makedir(path)
            logging.info(f"Directory created at {path}")
            if attr is not None:
                # Set file attributes if provided
                # Assuming attr includes permissions
                permissions = getattr(attr, 'st_mode', 0o755)
                self.fs.setinfo(path, {'details': {'permissions': permissions}})
            return SFTP_OK
        except OSError as e:
            logging.error(f"Failed to create directory {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def rmdir(self, path):
        try:
            self.fs.removedir(path)
            logging.info(f"Directory removed at {path}")
            return SFTP_OK
        except ResourceNotFound:
            logging.error(f"Directory not found: {path}")
            return SFTPServer.convert_errno(os.errno.ENOENT)
        except OSError as e:
            logging.error(f"Failed to remove directory {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)
        
    def chattr(self, path, attr):
        try:
            # Assuming attr includes permissions and potentially other metadata
            permissions = getattr(attr, 'st_mode', None)
            if permissions:
                self.fs.setinfo(path, {'details': {'permissions': permissions}})
            logging.info(f"Changed attributes for {path}: {attr}")
            return SFTP_OK
        except ResourceNotFound:
            logging.error(f"File not found for changing attributes: {path}")
            return SFTPServer.convert_errno(os.errno.ENOENT)
        except OSError as e:
            logging.error(f"Failed to change attributes for {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def readlink(self, path):
        try:
            symlink_target = self.fs.readlink(path)
            logging.info(f"Read symlink at {path}, target is {symlink_target}")
            return symlink_target
        except ResourceNotFound:
            logging.error(f"Symlink not found: {path}")
            return SFTPServer.convert_errno(os.errno.ENOENT)
        except OSError as e:
            logging.error(f"Failed to read symlink {path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)

    def symlink(self, target_path, path):
        try:
            self.fs.symlink(target_path, path)
            logging.info(f"Created symlink at {path} pointing to {target_path}")
            return SFTP_OK
        except ResourceNotFound:
            logging.error(f"Failed to create symlink due to missing target: {target_path}")
            return SFTPServer.convert_errno(os.errno.ENOENT)
        except OSError as e:
            logging.error(f"Failed to create symlink from {path} to {target_path}: {str(e)}")
            return SFTPServer.convert_errno(e.errno)
        
ssh_server = StubServer()