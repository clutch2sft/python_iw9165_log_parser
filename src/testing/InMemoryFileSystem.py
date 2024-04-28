import io
import os
import time
import threading
import logging
from stat import S_IFDIR, S_IFREG, S_ISDIR, S_IFLNK, S_IMODE, S_IFMT
from paramiko import SFTPAttributes

class SymbolicLink:
    def __init__(self, target):
        self.target = target


class InMemoryFileSystem:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InMemoryFileSystem, cls).__new__(cls)
                cls._instance.fs = {"/": (S_IFDIR | 0o755, None)}
                cls._instance.fs_lock = threading.RLock()
                # Setup logging
                if not logging.getLogger().hasHandlers():
                    logging.basicConfig(level=logging.DEBUG)
                cls._instance.logger = logging.getLogger('InMemoryFileSystem')
                cls._instance.logger.setLevel(logging.DEBUG)
            cls._instance.logger.debug("I'm initialized")
            print (f"Initalized logger is:{cls._instance.logger}")
            return cls._instance

    def __setitem__(self, key, value):
        """Allows setting items like a dictionary."""
        with self.fs_lock:
            self.fs[key] = value
            self.logger.debug(f"File {key} created/modified in in-memory file system.")

    def __getitem__(self, key):
        """Allows retrieving items like a dictionary."""
        with self.fs_lock:
            if key in self.fs:
                return self.fs[key]
            else:
                raise KeyError(f"File {key} not found in in-memory file system.")

    def __contains__(self, key):
        """Check if a file exists in the file system."""
        with self.fs_lock:
            return key in self.fs
        
    def realpath(self, path):
        try:
            normalized_path = os.path.normpath('/' + path.strip('/'))
            self.logger.debug(f"Normalized path: {normalized_path}")
            return normalized_path
        except Exception as e:
            self.logger.error(f"Error resolving path {path}: {e}")
            raise

    def readlink(self, path):
        with self.fs_lock:
            try:
                real_path = self.realpath(path)
                
                # Check if the path exists and if it's a symbolic link
                if real_path not in self.fs:
                    raise FileNotFoundError(f"No such file or directory: '{real_path}'")
                    
                mode, file_obj = self.fs[real_path]
                if not isinstance(file_obj, SymbolicLink):
                    raise OSError(f"Not a symbolic link: '{real_path}'")
                
                # Return the target of the symbolic link
                target = file_obj.target
                self.logger.debug(f"Read symbolic link '{real_path}' pointing to '{target}'")
                return target
            except Exception as e:
                self.logger.error(f"Error reading symbolic link {path}: {e}")
                raise


    def chattr(self, path, attr):
        with self.fs_lock:
            try:
                real_path = self.realpath(path)
                
                # Check if the path exists
                if real_path not in self.fs:
                    raise FileNotFoundError(f"No such file or directory: '{real_path}'")
                    
                # Update the file attributes
                mode, _ = self.fs[real_path]
                self.fs[real_path] = (S_IMODE(attr.st_mode) | S_IFMT(mode), None)
                
                self.logger.debug(f"Changed attributes for '{real_path}' to mode {attr.st_mode}")
            except Exception as e:
                self.logger.error(f"Error changing attributes for {path}: {e}")
                raise


    def rmdir(self, path):
        with self.fs_lock:
            try:
                real_path = self.realpath(path)
                
                # Check if the directory exists
                if real_path not in self.fs:
                    raise FileNotFoundError(f"No such file or directory: '{real_path}'")
                    
                # Check if the path is a directory
                if not S_ISDIR(self.fs[real_path][0]):
                    raise NotADirectoryError(f"Not a directory: '{real_path}'")
                    
                # Check if the directory is empty
                if any(child.startswith(real_path + '/') for child in self.fs if child != real_path):
                    raise OSError(f"Directory not empty: '{real_path}'")
                    
                # Remove the directory
                del self.fs[real_path]
                self.logger.debug(f"Removed directory '{real_path}'")
            except Exception as e:
                self.logger.error(f"Error removing directory {path}: {e}")
                raise


    def mkdir(self, path, mode):
        with self.fs_lock:
            try:
                real_path = self.realpath(path)
                
                if real_path in self.fs:
                    raise FileExistsError(f"Directory '{real_path}' already exists")
                    
                # Ensure that the parent directory exists
                parent_dir = os.path.dirname(real_path)
                if parent_dir != '/' and parent_dir not in self.fs:
                    raise FileNotFoundError(f"No such file or directory: '{parent_dir}'")
                    
                # Create the new directory
                self.fs[real_path] = (mode | S_IFDIR, io.BytesIO())
                self.logger.debug(f"Created directory '{real_path}'")
            except Exception as e:
                self.logger.error(f"Error creating directory {path}: {e}")
                raise


    def rename(self, old_path, new_path):
        with self.fs_lock:
            try:
                old_real_path = self.realpath(old_path)
                new_real_path = self.realpath(new_path)
                
                if old_real_path not in self.fs:
                    raise FileNotFoundError(f"No such file or directory: '{old_real_path}'")
                    
                if new_real_path in self.fs:
                    raise FileExistsError(f"Destination path '{new_real_path}' already exists")
                    
                self.fs[new_real_path] = self.fs.pop(old_real_path)
                self.logger.debug(f"Renamed '{old_real_path}' to '{new_real_path}'")
            except Exception as e:
                self.logger.error(f"Error renaming {old_path} to {new_path}: {e}")
                raise


    def remove(self, path):
        with self.fs_lock:
            try:
                real_path = self.realpath(path)
                if real_path in self.fs:
                    del self.fs[real_path]
                    self.logger.debug(f"Removed file or directory: {real_path}")
                else:
                    raise FileNotFoundError(f"No such file or directory: '{real_path}'")
            except Exception as e:
                self.logger.error(f"Error removing {path}: {e}")
                raise

    def open(self, path, flags, mode=0o100666):  # S_IFREG | 0o666
        with self.fs_lock:
            try:
                real_path = self.realpath(path)
                self.logger.debug(f"Opening file: {real_path} with flags: {flags}")
                if flags & os.O_CREAT or flags & os.O_WRONLY or flags & os.O_RDWR or flags & os.O_APPEND:
                    # Create or open the file for writing or appending
                    if real_path not in self.fs:
                        # Create the file if it does not exist
                        self.fs[real_path] = (mode, io.BytesIO())
                        self.logger.debug(f"File created: {real_path} with mode: {mode}")
                    return self.fs[real_path][1]
                elif flags & os.O_RDONLY:
                    # Open the file for reading
                    if real_path in self.fs:
                        self.logger.debug(f"File opened: {real_path} with mode: {mode}")
                        return self.fs[real_path][1]
                    else:
                        raise FileNotFoundError(f"No such file: {real_path}")
            except Exception as e:
                self.logger.error(f"Error opening file {path}: {e}")
                raise

    def read(self, file, size):
        try:
            self.logger.debug(f"Reading {size} bytes from file.")
            data = file.read(size)
            self.logger.debug(f"Read {len(data)} bytes from file.")
            return data
        except Exception as e:
            self.logger.error(f"Error reading from file: {e}")
            raise

    def write(self, file, data, offset=None):
        self.logger.debug(f"Writing data")
        with self.fs_lock:
            try:
                if offset is not None:
                    file.seek(offset)
                    self.logger.debug(f"Writing data at offset {offset}.")
                else:
                    file.seek(0, os.SEEK_END)
                    self.logger.debug("Appending data.")
                file.write(data)
                self.logger.debug(f"Wrote {len(data)} bytes to file.")
                return len(data)
            except Exception as e:
                self.logger.error(f"Error writing to file: {e}")
                raise

    def listdir(self, path):
        with self.fs_lock:
            try:
                real_path = self.realpath(path)
                contents = [p for p in self.fs if os.path.dirname(p) == real_path]
                self.logger.debug(f"Listing folder: {real_path} contents: {contents}")
                return contents
            except Exception as e:
                self.logger.error(f"Error listing folder {path}: {e}")
                raise

    def list_directory(self, path):
        with self.fs_lock:
            try:
                real_path = self.realpath(path)
                contents = [p for p in self.fs if os.path.dirname(p) == real_path]
                self.logger.debug(f"Listing folder: {real_path} contents: {contents}")
                return contents
            except Exception as e:
                self.logger.error(f"Error listing folder {path}: {e}")
                raise

    def close(self, file, path):
        with self.fs_lock:
            try:
                if file:
                    file.close()
                    # Optionally remove the file entry if it shouldn't persist after close
                    if path in self.fs:
                        del self.fs[path]
                        self.logger.debug(f"File at {path} closed and removed from filesystem.")
                else:
                    self.logger.warning("Attempted to close a NoneType file object.")
            except Exception as e:
                self.logger.error(f"Error closing file at {path}: {e}")
                raise


    def stat(self, path):
        with self.fs_lock:
            try:
                real_path = self.realpath(path)
                if real_path in self.fs:
                    mode, file_obj = self.fs[real_path]
                    size = file_obj.getbuffer().nbytes if file_obj else 0  # Get size for BytesIO, 0 for directories
                    # Prepare a simple stat result with fixed times as an example
                    attrs = SFTPAttributes()
                    attrs.st_mode = mode  # Directory or regular file
                    attrs.st_size = self.fs[path][1].getvalue()  # Example: size could be len(self.fs[path][1].getvalue()) for files
                    attrs.st_atime = attrs.st_mtime = attrs.st_ctime = time.time()
                    attrs.filename = path.split('/')[-1]  # Extract filename
                    return attrs
                else:
                    raise FileNotFoundError(f"No such file or directory: '{real_path}'")
            except Exception as e:
                self.logger.error(f"Error retrieving stats for {path}: {e}")
                raise

    def symlink(self, target, link_name):
        with self.fs_lock:
            try:
                # Resolve full paths
                real_target = self.realpath(target)
                real_link_name = self.realpath(link_name)

                # Check if the target exists (optional, depending on whether you want to allow broken links)
                if real_target not in self.fs:
                    raise FileNotFoundError(f"Target {target} does not exist.")

                # Ensure the link name does not already exist
                if real_link_name in self.fs:
                    raise FileExistsError(f"Link name {link_name} already exists.")

                # Create a symlink entry; assuming SymbolicLink is a class designed to handle symlink specifics
                self.fs[real_link_name] = (S_IFLNK | 0o777, SymbolicLink(target=real_target))
                self.logger.debug(f"Created symlink from {link_name} to {target}")
                
            except Exception as e:
                self.logger.error(f"Error creating symlink from {link_name} to {target}: {e}")
                raise

    def lstat(self, path):
        with self.fs_lock:
            try:
                real_path = self.realpath(path)
                if real_path in self.fs:
                    mode, file_obj = self.fs[real_path]

                    # Check if this is a symbolic link and adjust mode accordingly
                    if isinstance(file_obj, SymbolicLink):
                        # Report the link itself, not the target
                        size = len(file_obj.target)  # Typically the length of the symlink target path
                    else:
                        # Regular file or directory handling
                        size = file_obj.getbuffer().nbytes if file_obj else 0  # File size or 0 for directories

                    # Prepare the stat result, adjusting mode for symbolic links
                    stat_result = {
                        'st_mode': mode,
                        'st_ino': 0,
                        'st_dev': 0,
                        'st_nlink': 1,
                        'st_uid': 1000,  # Owner ID
                        'st_gid': 1000,  # Group ID
                        'st_size': size,
                        'st_atime': time.time(),  # Access time
                        'st_mtime': time.time(),  # Modification time
                        'st_ctime': time.time()  # Change time (metadata)
                    }
                    self.logger.debug(f"lstat for {path}: {stat_result}")
                    return stat_result
                else:
                    raise FileNotFoundError(f"No such file or directory: '{real_path}'")
            except Exception as e:
                self.logger.error(f"Error retrieving lstat for {path}: {e}")
                raise

    # Implement other SFTP-specific methods


    # Implement other SFTP-specific methods


# Example usage within your SFTP server class
# class InMemorySFTPServer:
#     def __init__(self):
#         self.filesystem = InMemoryFileSystem()

#     def handle_list_folder(self, path):
#         return self.filesystem.list_folder(path)

    # Additional methods to handle other SFTP operations
