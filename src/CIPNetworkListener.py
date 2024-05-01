import asyncio
import logging

class CIPNetworkListener:
    def __init__(self, host, port, use_udp=True, message_handler=None, logger=None):
        """
        Initialize the CIPNetworkListener with network settings and a message handler.

        :param host: The hostname or IP address to listen on.
        :param port: The port number to listen on.
        :param use_udp: Boolean flag to determine whether to use UDP (default) or TCP.
        :param message_handler: Function to handle incoming messages.
        :param logger: External logger for logging purposes.
        """
        self.host = host
        self.port = port
        self.use_udp = use_udp
        self.message_handler = message_handler
        self.logger = logger if logger else logging.getLogger('CIPNetworkListener')
        self.server = None  # To keep track of the server instance for shutdown

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
            lambda: UDPProtocol(self.message_handler, self.logger),
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
        """Handle incoming TCP connections and pass data to the message handler."""
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                if self.message_handler:
                    self.message_handler(data.decode())
        except Exception as e:
            self.logger.error(f"Error in TCP connection: {str(e)}")
        finally:
            writer.close()
            self.logger.info("TCP connection closed")

    async def shutdown(self):
        """Shutdown the server gracefully."""
        if self.server:
            self.server.close()
            if isinstance(self.server, asyncio.BaseServer):
                await self.server.wait_closed()
            self.logger.info("Server has been shutdown")
        else:
            self.logger.warning("No server is running to shut down")

class UDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, message_handler, logger):
        self.message_handler = message_handler
        self.logger = logger

    def datagram_received(self, data, addr):
        message = data.decode()
        self.logger.info(f"Received message from {addr}: {message}")
        if self.message_handler:
            self.message_handler(message)

    def error_received(self, exc):
        self.logger.error(f"UDP error received: {str(exc)}")

    def connection_lost(self, exc):
        if exc:
            self.logger.error(f"UDP connection lost: {str(exc)}")
        else:
            self.logger.info("UDP connection closed")
