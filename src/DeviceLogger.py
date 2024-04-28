import logging
from pathlib import Path
from threading import Lock
from datetime import datetime

class DeviceLogger:
    _loggers = {}
    _lock = Lock()

    @staticmethod
    def get_logger(ip_address, output_dir="logs", console_level=None, format=None, external_handler=None):
        """
        Returns a logger for the given IP address. If the logger does not already exist,
        it creates a new one with the specified settings, including an optional console logger.
        This method ensures that there is only one logger per device IP in a thread-safe manner.
        """
        with DeviceLogger._lock:
            if ip_address not in DeviceLogger._loggers:
                # Resolve the full path to the logs directory relative to the script location
                base_path = Path(__file__).resolve().parent.parent
                full_output_dir = base_path / output_dir
                DeviceLogger._setup_device_logger(ip_address, full_output_dir, console_level, format, external_handler)
        return DeviceLogger._loggers[ip_address]

    @staticmethod
    def _setup_device_logger(ip_address, output_dir, console_level, log_format, external_handler=None):
        """
        Set up a logger for each device with a unique file including a timestamp and optionally add an external handler.
        This function is internally called within a lock context.
        """
        output_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = output_dir / f"device_{ip_address}_{timestamp}.log"
        logger = logging.getLogger(f"device_{ip_address}")
        logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler(str(file_path))
        formatter = logging.Formatter(log_format or '%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        if console_level is not None:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(console_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        # Add the external handler if provided
        if external_handler:
            external_handler.setFormatter(formatter)
            external_handler.setLevel(logging.WARNING)
            logger.addHandler(external_handler)

        logger.propagate = False
        DeviceLogger._loggers[ip_address] = logger
