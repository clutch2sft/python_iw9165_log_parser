import re
from datetime import datetime
from ipaddress import ip_address

class CIPDataValidator:
    def __init__(self, allowed_chars=''):
        self.allowed_chars = allowed_chars

    def validate_ip(self, ip):
        try:
            ip_address(ip)
            return True
        except ValueError:
            return False

    def validate_date(self, date_str):
        try:
            if len(date_str) in (7, 8):
                standardized_date = f'{date_str[:2].zfill(2)}{date_str[2:4].zfill(2)}{date_str[4:]}'
                datetime.strptime(standardized_date, '%m%d%Y')
                return True
            return False
        except ValueError:
            return False

    def validate_error_string(self, err_str):
        return len(err_str) <= 48 and err_str.isalnum()

    def validate_shared_secret(self, secret):
        return len(secret) <= 48 and all(c.isalnum() or c in self.allowed_chars for c in secret)

    def validate_message(self, message, secret):
        parts = message.split(',')
        if len(parts) != 4:
            return False
        ip, date_str, error, secret = parts
        return (self.validate_ip(ip) and
                self.validate_date(date_str) and
                self.validate_error_string(error) and
                self.validate_shared_secret(secret))

# Usage within your network classes
# class UDPProtocol(asyncio.DatagramProtocol):
#     def __init__(self, logger):
#         self.logger = logger
#         self.validator = DataValidator()

#     def datagram_received(self, data, addr):
#         message = data.decode()
#         if not self.validator.validate_message(message):
#             self.logger.error(f"Invalid message format from {addr}")
#             return
#         self.logger.info(f"Validated and received message from {addr}: {message}")
#         dispatcher.send(signal="NetworkDataReceived", sender="UDPConnection", data=message)

# # Similar setup for TCP handling
