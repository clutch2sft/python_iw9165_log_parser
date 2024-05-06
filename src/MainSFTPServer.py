import socket
import threading
import paramiko
import traceback
from stub_sftp_server import StubSFTPServer
from stub_server import StubServer

class MainSFTPServer:
    def __init__(self, fs, logger):
        self.fs = fs
        self.logger = logger
        self.server_socket = None
        self.server_key = paramiko.RSAKey.generate(bits=1024)
        self.active = False
        self.lock = threading.Lock()
        self.threads = []
        self.ssh_server = StubServer()  # Create an instance of StubServer here


    def _setup_transport(self, connection):
        transport = paramiko.Transport(connection)
        transport.add_server_key(self.server_key)
        transport.set_subsystem_handler(
            'sftp', 
            paramiko.SFTPServer, 
            lambda channel, *args: self._sftp_server_factory(channel, 'sftp', self.ssh_server, self.fs, *args)
        )
        transport.start_server(server=self.ssh_server)
        self.logger.debug("Transport layer set up and started.")
        return transport

    def _sftp_server_factory(self, channel, name, server, fs, *args):
        self.logger.debug(f"SFTP server factory called for channel: {name}")
        return StubSFTPServer(channel, name, server, fs, self.logger, *args)


    def _handle_connection(self, connection):
        transport = None
        try:
            transport = self._setup_transport(connection)
            while True:
                channel = transport.accept()
                if channel is None:
                    self.logger.info("No more channels. Closing transport.")
                    break
                self.logger.info("Channel accepted and session started.")
                # Process the channel here
        except EOFError:
            self.logger.info("Client disconnected unexpectedly.")
        except paramiko.ssh_exception.SSHException as e:
            # Log only the error message without the traceback
            self.logger.error(f"SSH protocol error: {str(e)}")
            # Optionally log the full traceback to a file or as debug
            self.logger.debug(f"Full traceback: {traceback.format_exc()}")
        except Exception as e:
            # Generic handler for other unexpected issues
            self.logger.error(f"Unhandled error: {str(e)}")
            # Optionally log the full traceback to a file or as debug
            self.logger.debug(f"Full traceback: {traceback.format_exc()}")
        finally:
            if transport:
                transport.close()
                self.logger.info("Transport closed.")



    def start_server(self):
        with self.lock:
            if not self.active:
                self.active = True
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
                self.server_socket.bind(('localhost', 3373))
                self.server_socket.listen(10)
                self.logger.info("Server listening on localhost:3373")

        try:
            while self.active:
                connection, _ = self.server_socket.accept()
                self.logger.info("Connection accepted.")
                thread = threading.Thread(target=self._handle_connection, args=(connection,))
                thread.start()
                self.threads.append(thread)
        except Exception as e:
            self.logger.error(f"Error during server operation: {str(e)}")
        finally:
            self.stop_server()

    def stop_server(self):
        with self.lock:
            if self.active:
                self.active = False
                self.server_socket.close()
                self.logger.info("Server has been stopped.")
                for thread in self.threads:
                    thread.join()
