import asyncio
import asyncssh
import requests
from typing import Optional, Dict
from CIPEventManager import CIPEventManager  # Ensure this is correctly imported

class CiscoDeviceManager:
    def __init__(self, default_device_config: Dict[str, any], external_handler=None, logger=None):
        """
        Initialize with a device configuration.
        :param device_config: A dictionary containing device parameters.
        """
        self.default_device_config = default_device_config
        self.connection = None
        self.device_logger = logger

    async def fetch_credentials(self, ip: str) -> Optional[Dict[str, str]]:
        """
        Fetch credentials securely based on the IP address.
        """
        try:
            #TODO: Push url and ip into configuration
            response = await asyncio.to_thread(requests.get, f"https://your-credential-api.example.com/credentials?ip={ip}")
            response.raise_for_status()
            credentials = response.json()
            return credentials
        except requests.RequestException as e:
            self.device_logger.error(f"Failed to fetch credentials: {e}")
            return None

    async def connect_and_retrieve_logs(self, sender, **kw):
        """
        Connects to the device using dynamically fetched credentials and retrieves logs.
        """
        event_id = kw['event_id']
        event_manager = CIPEventManager()
        event = await event_manager.get_event(event_id)

        if event:
            ip = event.ip  # Assuming the event object has an 'ip' attribute
            credentials = await self.fetch_credentials(ip)
            if not credentials:
                self.device_logger.error(f"No credentials available for IP {ip}")
                return  # Handle lack of credentials appropriately

            # Prepare device configuration
            device_config = self.default_device_config.copy()
            device_config.update({
                'host': ip,
                'username': credentials['username'],
                'password': credentials['password'],
                'known_hosts': None  # You should handle known hosts in a production environment
            })

            # Attempt to connect and retrieve logs
            try:
                async with asyncssh.connect(**device_config) as conn:
                    self.connection = conn
                    log_output = await self.retrieve_events(event_id)
                    self.device_logger.info(f"Logs retrieved for event {event_id}: {log_output}")
            except (asyncssh.Error, Exception) as e:
                self.device_logger.error(f"SSH connection failed: {e}")
            finally:
                if self.connection:
                    await self.connection.close()
                    self.device_logger.warning("Disconnected from the device successfully.")
        else:
            self.device_logger.error(f"Failed to retrieve event data for event_id: {event_id}")

    async def retrieve_events(self, event_id: str) -> str:
        """
        Retrieves logs or events from the Cisco device.
        Returns the event log as a string.
        """
        if not self.connection:
            self.device_logger.warning("Not connected to any device.")
            return ""

        #TODO: push this ip (1.1.1.1) into configuration
        log_output = await self.connection.run(f'copy event-logging upload tftp://1.1.1.1/{event_id}.tar.gz')
        self.device_logger.info(log_output)
        return log_output.stdout

