import os
from pydispatch import dispatcher

class AsyncSFTPHandle:
    def __init__(self, file_obj, fs, path, logger):
        self.file_obj = file_obj
        self.fs = fs
        self.path = path
        self.custom_logger = logger
        self.last_operation = None  # Track the last operation ('read' or 'write')
        self.custom_logger.debug(f"AsyncSFTPHandle was instantiated here for path: {path}")

    def seek(self, offset, whence=os.SEEK_SET):
        """Perform the seek operation synchronously."""
        method_name = self.seek.__name__
        class_name = self.__class__.__name__
        self.custom_logger.debug(f"{class_name}:{method_name} Seeking to {offset} in {self.path}")
        self.file_obj.seek(offset, whence)

    def read(self, length):
        method_name = self.read.__name__
        class_name = self.__class__.__name__
        """Read a segment of the file at a given offset."""
        self.custom_logger.debug(f"Attempting to read {length} bytes from {self.path}")
        data = self.file_obj.read(length)
        self.custom_logger.debug(f"{class_name}:{method_name} Read {len(data)} bytes from {self.path}")
        self.last_operation = 'read'  # Update last operation to 'read'
        return data

    def write(self, data):
        method_name = self.write.__name__
        class_name = self.__class__.__name__
        """Write data synchronously after seeking to the correct offset."""
        bytes_written = self.file_obj.write(data)
        self.custom_logger.debug(f"{class_name}:{method_name} Wrote {bytes_written} bytes to {self.path}")
        self.last_operation = 'write'  # Update last operation to 'write'
        return bytes_written

    def close(self):
        method_name = self.close.__name__
        class_name = self.__class__.__name__
        """Log the file closing action; conditionally dispatch based on last operation."""
        self.custom_logger.info(f"Closed file handle for {self.path}")
        self.file_obj.close()  # Ensure any necessary cleanup operations are performed if applicable
        if self.last_operation == 'write':
            # Only emit event if the last operation was a write
            self.custom_logger.info(f"{class_name}:{method_name} Dispatched FileReceived for {self.path}")
            dispatcher.send(signal="FileReceived", sender=self, path=self.path, fs=self.fs, logger=self.custom_logger)
