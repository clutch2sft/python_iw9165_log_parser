import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
print (sys.path)

import asyncio
import unittest
from unittest.mock import MagicMock, patch
from unittest.mock import AsyncMock
from CIPNetworkListener import CIPNetworkListener  # Import your class


# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
# print (sys.path)


class TestCIPNetworkListener(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Mock logger to pass into the listener
        self.mock_logger = MagicMock()
        # Create an instance of the listener
        self.listener = CIPNetworkListener('localhost', 9999, logger=self.mock_logger)

    @patch('asyncio.get_running_loop')
    async def test_start_udp_server(self, mock_loop):
        # Use AsyncMock for Python 3.8 and above
        mock_loop.return_value.create_datagram_endpoint = AsyncMock(return_value=(MagicMock(), MagicMock()))
        
        # Start the UDP server
        await self.listener.start_udp_server()
        
        # Assert the server is set and logger called
        self.assertIsNotNone(self.listener.server)
        self.mock_logger.info.assert_called_with('UDP Server listening on localhost:9999')

    @patch('asyncio.start_server')
    async def test_start_tcp_server(self, mock_start_server):
        # Setup the start_server to return a mock server directly
        mock_server = MagicMock()
        mock_start_server.return_value = mock_server
        
        # Start the TCP server
        server = await self.listener.start_tcp_server()
        
        # Assert server is returned and logger called
        self.assertEqual(server, mock_server)
        self.mock_logger.info.assert_called_with('TCP Server listening on localhost:9999')
        async def test_shutdown(self):
            # Assuming the listener has a server
            mock_server = MagicMock()
            self.listener.server = mock_server
            
            # Perform the shutdown
            await self.listener.shutdown()
            
            # Assert the server close was called
            mock_server.close.assert_called_once()
            self.mock_logger.info.assert_called_with("Server has been shutdown")

if __name__ == '__main__':
    unittest.main()