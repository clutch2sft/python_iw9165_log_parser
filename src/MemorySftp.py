from paramiko.sftp_server import SFTPHandle, SFTPServerInterface
from ConfigurationLoader import ConfigLoader
from DeviceLogger import DeviceLogger
import tarfile, io, datetime, logging
from collections import defaultdict
import paramiko, os


class MemorySFTPHandle(SFTPHandle):
    """Custom SFTP handle to manage in-memory files."""
    def __init__(self, filelike, callback, identifier):
        super(MemorySFTPHandle, self).__init__(flags=0)
        self.filelike = filelike
        self.callback = callback
        self.identifier = identifier

class MemorySFTPServer(SFTPServerInterface):
    def __init__(self, server, *args, **kwargs):
        self.server = server
        self.files = defaultdict(dict)
        self.callback = kwargs.get('callback', lambda x: None)
        # Set up logger
        config_loader = ConfigLoader()
        config = config_loader.get_configuration()
        output_dir = config['output_dir']
        log_format = config['log_format']
        console_level = getattr(logging, config.get('console_level', 'INFO')) if config.get('console_level', None) else None
        self.logger = DeviceLogger.get_logger("sftpserver", output_dir, console_level=console_level, format=log_format, external_handler=False)
    # def check_auth_password(self, username, password):
    #     # Implement your logic to check username and password
    #     if username == "user" and password == "pass":
    #         return paramiko.AUTH_SUCCESSFUL
    #     return paramiko.AUTH_FAILED
    def enable_auth_gssapi(self):
        """Explicitly disable GSS-API authentication."""
        return False
    def get_banner(self):
        # Optionally return a banner message or None
        return "Welcome to MemorySFTPServer!", "en-US"
    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        # Implement your password check here
        return paramiko.AUTH_SUCCESSFUL

    def check_auth_publickey(self, username, key):
        # Implement your public key check here
        return paramiko.AUTH_SUCCESSFUL

    def get_allowed_auths(self, username):
        return 'password,publickey'

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

    def check_channel_env_request(self, channel, name, value):
        return True
    
    def check_auth_none(self, password):
        return paramiko.AUTH_SUCCESSFUL

    def check_channel_subsystem_request(self, channel, name):
        if name == "sftp":
            self.logger.warning(f"SFTP subsystem requested on channel {channel.get_id()}")
            # Instantiate your MemorySFTPServer directly here to handle the SFTP session
            self.sftp_server = MemorySFTPServer(channel)
            return True
        return False


    # def check_channel_exec_request(self, channel, command):
    #     print(f"{command}")
    #     return True

    # Include the logging in file methods called by paramiko (open and close)
    def open(self, path, flags, attr):
        self.logger.warning("in open file")
        filename = path.split("/")[-1]
        if filename.endswith('.tar.gz'):
            identifier = self.generate_identifier(self.server.client_address[0])
            self.logger.info(f"Opening file: {filename} with identifier {identifier}")
            return MemorySFTPHandle(io.BytesIO(), self.callback, identifier)
        else:
            self.logger.error("Attempted to open a non-supported file type.")
            return IOError("Only .tar.gz files are supported")

    def close(self, handle):
        handle.filelike.seek(0)
        tar = tarfile.open(fileobj=handle.filelike, mode="r:gz")
        for member in tar.getmembers():
            if member.isfile():
                file_content = tar.extractfile(member).read()
                self.files[handle.identifier][member.name] = io.BytesIO(file_content)
        tar.close()
        # Notify that new files are ready for analysis
        handle.callback(handle.identifier, self)
    def stat(self, path):
        try:
            st = os.stat(path)
            return paramiko.SFTPAttributes.from_stat(st)
        except OSError as e:
            return paramiko.SFTPIOError(e.errno, str(e))

    def list_folder(self, path):
        try:
            out = []
            for fname in os.listdir(path):
                attr = paramiko.SFTPAttributes.from_stat(os.stat(os.path.join(path, fname)))
                attr.filename = fname
                out.append(attr)
            return out
        except OSError as e:
            return paramiko.SFTPIOError(e.errno, str(e))

    def read(self, handle, offset, length):
        try:
            handle.filelike.seek(offset)
            return handle.filelike.read(length)
        except IOError as e:
            return paramiko.SFTPIOError(e.errno, str(e))

    def write(self, handle, offset, data):
        try:
            handle.filelike.seek(offset)
            handle.filelike.write(data)
            return len(data)
        except IOError as e:
            return paramiko.SFTPIOError(e.errno, str(e))
        
    def generate_identifier(self, ip_address):
        """Generate a unique identifier using the IP address and a timestamp."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{ip_address}_{timestamp}"

    def get_files(self, identifier):
        """Return the file contents from memory for a specific upload identifier."""
        return {name: file.getvalue() for name, file in self.files[identifier].items()}

class SFTPHandler(paramiko.SFTPHandle):
    def __init__(self, channel):
        super(SFTPHandler, self).__init__(channel)
        # Set up logger
        config_loader = ConfigLoader()
        config = config_loader.get_configuration()
        output_dir = config['output_dir']
        log_format = config['log_format']
        console_level = getattr(logging, config.get('console_level', 'INFO')) if config.get('console_level', None) else None
        self.logger = DeviceLogger.get_logger("sftpserver", output_dir, console_level=console_level, format=log_format, external_handler=False)
        self.logger.info("SFTP session started")
        # Initialize your SFTP environment here
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
        
        
    def start_subsystem(self, name, transport, channel):
        # Set up your SFTP server session here
        self.server = paramiko.SFTPServer(channel)
        self.server.serve_forever()


# from threading import Thread
# import paramiko
# import socket

# def notification_callback(identifier):
#     print(f"New files are ready for analysis from {identifier}")

# def start_sftp_server(port=2222):
#     host_key = paramiko.RSAKey.generate(1024)

#     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
#     sock.bind(("localhost", port))
#     sock.listen(1)

#     print(f"SFTP server running on port {port}...")

#     while True:
#         client, addr = sock.accept()
#         print(f"Connected to {addr}")
#         transport = paramiko.Transport(client)
#         transport.add_server_key(host_key)
#         server = MemorySFTPServer(transport, callback=notification_callback)
#         transport.start_server(server=server)

#         while transport.is_active():
#             pass  # Handle server timeout or similar logic here

# if __name__ == "__main__":
#     Thread(target=start_sftp_server, daemon=True).start()
#     input("Press Enter to stop the server...\n")