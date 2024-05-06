import os

class AsyncSFTPHandle:
    def __init__(self, file_obj, fs, path, logger):
        self.file_obj = file_obj
        self.fs = fs
        self.path = path
        self.custom_logger = logger
        self.custom_logger.debug(f"AsyncSFTPHandle was instantiated here for path: {path}")

    def seek(self, offset, whence=os.SEEK_SET):
        """Perform the seek operation synchronously."""
        self.custom_logger.debug(f"Seeking to {offset} in {self.path}")
        self.file_obj.seek(offset, whence)

    def read(self, offset, length):
        """Read data synchronously after seeking to the correct offset."""
        self.seek(offset)
        data = self.file_obj.read(length)
        self.custom_logger.debug(f"Read {len(data)} bytes from {self.path} at offset {offset}")
        return data

    def write(self, data):
        """Write data synchronously after seeking to the correct offset."""
        bytes_written = self.file_obj.write(data)
        self.custom_logger.debug(f"Wrote {bytes_written} bytes to {self.path}")
        return bytes_written

    def close(self):
        """Log the file closing action; no actual file closing necessary with MemoryFS."""
        self.custom_logger.info(f"Closed file handle for {self.path}")
        self.file_obj.close()  # Ensure any necessary cleanup operations are performed if applicable
