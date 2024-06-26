import asyncio, struct, socket
import logging
from pydispatch import dispatcher
from CIPDataValidation import CIPDataValidator
class CIPNetworkListener:
    def __init__(self, host, port, use_udp=True, logger=None, config=None):
        """
        Initialize the CIPNetworkListener with network settings.

        :param host: The hostname or IP address to listen on.
        :param port: The port number to listen on.
        :param use_udp: Boolean flag to determine whether to use UDP (default) or TCP.
        :param logger: External logger for logging purposes.
        """
        self.host = host
        self.port = port
        self.use_udp = use_udp
        self.logger = logger if logger else logging.getLogger('CIPNetworkListener')
        self.server = None  # To keep track of the server instance for shutdown
        self.shared_secret = config['shared_secret']
        self.validator = CIPDataValidator()
        self.config = config

    async def start_server(self):
        """Starts the server to listen for incoming messages based on the protocol."""
        if self.use_udp:
            self.logger.info("Starting UDP server")
            await self.start_udp_server()
        else:
            self.logger.info("Starting TCP server")
            self.server = await self.start_tcp_server()

    async def start_udp_server(self):
        """Start a UDP server."""
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self.logger, config=self.config),
            local_addr=(self.host, self.port))
        self.server = transport
        self.logger.info(f"UDP Server listening on {self.host}:{self.port}")

    async def start_tcp_server(self):
        """Start a TCP server."""
        server = await asyncio.start_server(
            self.handle_tcp_connection,
            self.host, self.port)
        self.logger.info(f"TCP Server listening on {self.host}:{self.port}")
        return server

    async def handle_tcp_connection(self, reader, writer):
        addr = writer.get_extra_info('peername')  # Get client address if needed for logging
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break  # Stop if no data is received
                ip = socket.inet_ntoa(data[0:4])  # Extract and convert the IP address
                datetime, = struct.unpack('>I', data[4:8])  # Unpack the datetime integer
                error_code = data[8:16].decode('ascii').strip('\x00')  # Decode the error code
                shared_secret = data[16:].decode('ascii').strip('\x00')  # Decode the shared secret
                
                # Now we create a structured message dictionary to validate and process
                message = {
                    'ip': ip,
                    'datetime': datetime,
                    'error_code': error_code,
                    'shared_secret': shared_secret
                }
                if not self.validator.validate_message(message, self.shared_secret ):
                    self.logger.error(f"Invalid message format from {addr}")
                    writer.close()  # Optionally close the connection if the message is invalid
                    return
                # Emit event after validation
                dispatcher.send(signal="NetworkDataReceived", sender="TCPConnection", data=message)
        except Exception as e:
            self.logger.error(f"Error in TCP connection from {addr}: {str(e)}")
        finally:
            writer.close()
            self.logger.info(f"TCP connection with {addr} closed")

    async def shutdown(self):
        """Shutdown the server gracefully."""
        if self.server:
            self.server.close()
            if isinstance(self.server, asyncio.Server):
                await self.server.wait_closed()
            self.logger.info("Server has been shutdown")

class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, logger, config=None):
        self.logger = logger
        self.shared_secret = config['shared_secret']
        self.validator = CIPDataValidator()

    def datagram_received(self, data, addr):
        message = data.decode()
        if not self.validator.validate_message(message, self.shared_secret ):
            self.logger.error(f"Invalid message format from {addr}")
            return
        self.logger.info(f"Received message from {addr}: {message}")
        # Emit event instead of direct handling
        dispatcher.send(signal="NetworkDataReceived", sender="UDPConnection", data=message)

    def error_received(self, exc):
        self.logger.error(f"UDP error received: {str(exc)}")

    def connection_lost(self, exc):
        if exc:
            self.logger.error(f"UDP connection lost: {str(exc)}")
        else:
            self.logger.info("UDP connection closed")
