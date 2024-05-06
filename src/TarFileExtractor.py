import tarfile
import datetime
import os
from pydispatch import dispatcher


class TarFileExtractor:
    def __init__(self, logger, fs = None):
        """
        Initializes the TarFileExtractor with a logger.
        
        :param fs: The filesystem object to interact with files (can be set later).
        :param logger: Logger instance for logging information.
        """
        self.fs = fs
        self.logger = logger
        self.extracted_items = []  # List to store paths of extracted files and directories
        dispatcher.connect(self.handle_file_received, signal="FileReceived", sender=dispatcher.Any)

    def handle_file_received(self, sender, **kwargs):
        self.fs = kwargs.get('fs')
        self.tar_path = kwargs.get('path')
        self.unique_dir = None  # Reset or create a new directory for each file
        filename = os.path.basename(self.tar_path)
        self.event_id = filename.split('.')[0]  # Assuming the format "event_id.tar.gz"
        self.extract_files()

    def extract_files(self):
        if not self.unique_dir:
            self.unique_dir = self._create_unique_directory()

        try:
            with self.fs.open(self.tar_path, mode='rb') as file_obj:
                with tarfile.open(fileobj=file_obj, mode='r:gz') as tar:
                    for member in tar.getmembers():
                        member_path = f"{self.unique_dir}/{member.name}"
                        if member.isdir():
                            self.fs.makedirs(member_path, recreate=True)
                        elif member.isfile():
                            with tar.extractfile(member) as source_file:
                                contents = source_file.read()
                                with self.fs.open(member_path, 'wb') as dest_file:
                                    dest_file.write(contents)
                                    self.extracted_items.append(member_path)
                # Close the tar file after extraction
                tar.close()

            # Log extraction success
            self.logger.info(f"Extracted {self.tar_path} to {self.unique_dir}")

            # Remove the original tar file after successful extraction
            self.fs.remove(self.tar_path)
            self.logger.info(f"Removed original tar file: {self.tar_path}")

            # Emit the custom event with the directory and the list of extracted items
            dispatcher.send(signal="ExtractionCompleted", sender=self, directory=self.unique_dir, extracted_items=self.extracted_items, event_id=self.event_id)

        except Exception as e:
            self.logger.error(f"Error extracting {self.tar_path}: {str(e)}")
            # Optionally clean up the created directory on failure
            if self.unique_dir and 'extract_' in self.unique_dir:
                self.fs.removetree(self.unique_dir)
                self.logger.info(f"Cleaned up directory due to error: {self.unique_dir}")


    def _create_unique_directory(self):
        base_path = "/extracts"
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        unique_dir = f"{base_path}/extract_{timestamp}"
        self.fs.makedirs(unique_dir, recreate=True)
        return unique_dir