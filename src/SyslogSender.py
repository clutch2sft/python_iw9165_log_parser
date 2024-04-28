import socket
from datetime import datetime

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
        return cls._instance

    def _setup_socket(self):
        if self.transport.lower() == 'tcp':
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.ip, self.port))
        else:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_events(self, events, source_ip):
        timestamp = datetime.now().strftime("%b %d %H:%M:%S")
        app = "IWPLOGPARSER"
        try:
            for event in events:
                # Format follows RFC 3164 for better compatibility with default rsyslog
                message = f"<134>{timestamp} {source_ip} {app} {event}\n"
                if self.transport.lower() == 'tcp':
                    self.sock.sendall(message.encode('utf-8'))
                else:
                    self.sock.sendto(message.encode('utf-8'), (self.ip, self.port))
            self.logger.info("Events successfully sent to syslog server.")
        except Exception as e:
            self.logger.error(f"Failed to send events: {str(e)}")

    def __del__(self):
        if self.sock:
            self.sock.close()
            self.logger.info("Syslog sender socket closed.")
