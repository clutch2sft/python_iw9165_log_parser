from netmiko import ConnectHandler
from typing import List
from ConfigurationLoader import ConfigLoader
from DeviceLogger import DeviceLogger
import logging

class CiscoDeviceManager:
    def __init__(self, device_config: dict, external_handler=None):
        """
        Initialize with a device configuration.
        :param device_config: A dictionary containing device parameters.
        """
        self.device_config = device_config
        self.connection = None
        self.ip = device_config['ip']
        config_loader = ConfigLoader()
        config = config_loader.get_configuration()
        self.output_dir = config['output_dir']
        self.console_level = None if external_handler else config.get('console_level', None)
        self.log_format = config['log_format']

        # Convert console_level string to actual logging level if needed
        console_level = getattr(logging, self.console_level) if self.console_level else None
        self.device_logger = DeviceLogger.get_logger(self.ip, self.output_dir, console_level=console_level, format=self.log_format, external_handler=external_handler)

    def connect(self):
        """
        Establishes a connection to the Cisco device.
        """
        self.connection = ConnectHandler(**self.device_config)
        self.device_logger.warning(f"Connected to the device successfully.")

    def retrieve_events(self) -> str:
        """
        Retrieves logs or events from the Cisco device.
        Returns the event log as a string.
        """
        if not self.connection:
            self.device_logger.warning(f"Not connected to any device.")
            return ""

        # Example command to retrieve logs, adjust as per your device's configuration
        log_output = self.connection.send_command("show logging")
        return log_output


    def disconnect(self):
        """
        Safely disconnect from the device.
        """
        if self.connection:
            self.connection.disconnect()
            self.device_logger.warning(f"Disconnected from the device successfully.")
