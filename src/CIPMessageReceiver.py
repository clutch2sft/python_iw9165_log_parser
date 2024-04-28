from pycomm3 import LogixDriver

class CIPMessageReceiver:
    def __init__(self, plc_address, logger):
        self.plc_address = plc_address
        self.logger = logger

    def handle_fault_message(self, tag):
        """
        Handle incoming fault message by reading the fault tag from the PLC.
        """
        with LogixDriver(self.plc_address) as plc:
            fault_info = plc.read(tag)
            if fault_info:
                self.logger.info(f"Fault detected: {fault_info.value}")
                self.process_fault(fault_info.value)
            else:
                self.logger.error("Failed to read fault information from PLC.")

    def process_fault(self, fault_data):
        """
        Process the fault data to determine the response or action required.
        """
        # Example: Log the fault, notify systems, or trigger corrective actions
        self.logger.info(f"Processing fault: {fault_data}")
