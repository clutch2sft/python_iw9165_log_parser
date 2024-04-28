import logging
import socket
import paramiko
from stub_sftp import StubSFTPServer, ssh_server
from fs.memoryfs import MemoryFS

# Configuration
HOST, PORT = 'localhost', 3373
ROOT = '/virtual_root'




log_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
# # Setup specific logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
logging.basicConfig(format=log_format)
# - setup paramiko logging
paramiko_logger = logging.getLogger('paramiko')
paramiko_logger.setLevel(logging.INFO)




def setup_file_system():
    # Create a MemoryFS instance
    shared_fs = MemoryFS()
    #shared_fs.makedirs(ROOT, recreate=True)
    #logger.debug("File system setup at root: %s", ROOT)
    logger.debug("File system setup at root")
    return shared_fs

def setup_transport(connection, srv_fs, server_key):
    transport = paramiko.Transport(connection)
    transport.add_server_key(server_key)
    transport.set_subsystem_handler(
        'sftp',
        paramiko.SFTPServer,
        lambda channel, *args: sftp_server_factory(channel, 'sftp', ssh_server, srv_fs, *args)
    )
    transport.start_server(server=ssh_server)
    logger.debug("Transport layer set up and started.")
    return transport

def sftp_server_factory(channel, name, server, shared_fs, *args):
    logger.debug("SFTP server factory called for channel: %s", name)
    return StubSFTPServer(channel, name, server, shared_fs, *args)

def start_server(srv_fs):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    server_socket.bind((HOST, PORT))
    server_socket.listen(10)  # Single connection at a time
    logger.info("Server listening on %s:%d", HOST, PORT)

    # Generate a consistent server key
    server_key = paramiko.RSAKey.generate(bits=1024)
    sessions = []
    try:
        while True:
            connection, _ = server_socket.accept()
            logger.info("Connection accepted. Starting a new thread")
            transport = setup_transport(connection, srv_fs, server_key)
            #channel = transport.accept(timeout=20)
            channel = transport.accept()
            sessions.append(channel)
            logger.info("Channel accepted and session started.")
            logger.debug('%s active sessions new channel: %i', len(sessions), channel.chanid)
            # handle_channel(channel)  # You would need to define this function
    except Exception as e:
        logger.error("Error during session handling: %s", str(e))
    finally:
        logger.info("Session ended.")
        transport.close()  # Ensure transport is closed properly

def handle_channel(channel):
    try:
        while not channel.closed:
            # Implement how you want to handle channel data or requests
            pass
    finally:
        channel.close()

def main():
    srv_fs = setup_file_system()
    start_server(srv_fs)

if __name__ == '__main__':
    main()
