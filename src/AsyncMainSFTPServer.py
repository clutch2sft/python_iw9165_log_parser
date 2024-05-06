import asyncssh
from AsyncMySSHSever import AsyncMySSHServer
from AsyncSFTPServer import AsyncSFTPServer

class AsyncMainSFTPServer:
    def __init__(self, host, port, fs, logger, config = None):
        self.host = host
        self.port = port
        self.fs = fs
        self.custom_logger = logger
        if config:
            self.server_host_key = config['sftp_rsa_keyfile']
            self.host = config['sftp_host_ip']
            self.port = config['sftp_listen_port']
        else:
            self.server_host_key = "/path/to/keyfile"
            self.host = "localhost"
            self.port = 3373


    async def start_sftp_server(self):
        self.custom_logger.info(f'Starting SFTP server on {self.host}:{self.port}')
        await asyncssh.listen(
            host=self.host,
            port=self.port,
            server_host_keys=[self.server_host_key],
            sftp_factory=self.create_sftp_server,
            server_factory=lambda: AsyncMySSHServer(self.custom_logger)  # Create a new instance of MySSHServer for each connection
        )

    def create_sftp_server(self, conn):
        # Create and return an instance of AsyncSFTPServer for each connection
        return AsyncSFTPServer(conn, self.fs, self.custom_logger)