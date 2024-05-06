from pydispatch import dispatcher
import socket
from datetime import datetime
from CIPEventManager import CIPEventManager
class SyslogSender:
    _instance = None

    def __new__(cls, logger, ip, port, transport='udp'):
        if cls._instance is None:
            cls._instance = super(SyslogSender, cls).__new__(cls)
            cls._instance.logger = logger
            cls._instance.ip = ip
            cls._instance.port = port
            cls._instance.transport = transport
            cls._instance._setup_socket()
            dispatcher.connect(cls._instance.handle_log_processing_completed, signal="LogProcessingCompleted", sender=dispatcher.Any)
        return cls._instance

    def _setup_socket(self):
        if self.transport.lower() == 'tcp':
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.ip, self.port))
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def handle_log_processing_completed(self, sender, **kwargs):
        event_id = kwargs['event_id']
        event_manager = CIPEventManager.get_instance()
        event = event_manager.get_event(event_id)
        if event:
            source_ip = event_id.split('_')[0]  # Assuming event_id is in the format "ip_datetime"
            if event.categorized_logs:
                for category, logs in event.categorized_logs.items():
                    self.send_events(logs, source_ip, category)
            else:
                self.logger.error(f"No categorized logs found for event ID {event_id}")
        else:
            self.logger.error(f"Event not found with ID {event_id}")

    def send_events(self, events, source_ip, category):
        timestamp = datetime.now().strftime("%b %d %H:%M:%S")
        app = "IWPLOGPARSER"
        try:
            for event in events:
                message = f"<134>{timestamp} {source_ip} {app} {category}: {event}\n"
                if self.transport.lower() == 'tcp':
                    self.sock.sendall(message.encode('utf-8'))
                else:
                    self.sock.sendto(message.encode('utf-8'), (self.ip, self.port))
            self.logger.info(f"Events successfully sent to syslog server under category '{category}'.")
        except Exception as e:
            self.logger.error(f"Failed to send events: {str(e)}")

    def __del__(self):
        if self.sock:
            self.sock.close()
            self.logger.info("Syslog sender socket closed.")
