from pycomm3 import LogixDriver

class CIPResponseManager:
    def __init__(self, logger, plc_address):
        """
        Initializes the CIPResponseManager with a logger and the address of the PLC.
        
        :param logger: A logging object to log responses and errors.
        :param plc_address: The IP address of the PLC for sending responses.
        """
        self.logger = logger
        self.plc_address = plc_address

    def send_response(self, tag_name, value):
        """
        Sends a response or command to the PLC by writing a tag.
        
        :param tag_name: The tag to write to on the PLC.
        :param value: The value to write to the tag.
        """
        try:
            with LogixDriver(self.plc_address) as plc:
                result = plc.write(tag_name, value)
                if result:
                    self.logger.info(f"Successfully wrote {value} to {tag_name}")
                else:
                    self.logger.error(f"Failed to write to {tag_name}")
        except Exception as e:
            self.logger.error(f"Failed to send response to PLC: {str(e)}")
