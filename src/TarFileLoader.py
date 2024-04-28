import os
import tarfile
import io
import datetime
from collections import defaultdict

class TarFileLoader:
    def __init__(self, directory, callback, logger):
        """
        Initializes the FileLoader with a directory and a callback function.
        :param directory: The directory to load .tar.gz files from.
        :param callback: Function to call after files are processed.
        :param logger: Logger instance for logging information.
        """
        self.directory = directory
        self.callback = callback
        self.logger = logger
        self.files = defaultdict(dict)

    def load_files(self):
        """
        Loads all .tar.gz files from the specified directory and processes them.
        """
        for filename in os.listdir(self.directory):
            if filename.endswith('.tar.gz'):
                file_path = os.path.join(self.directory, filename)
                self.process_file(file_path, filename)

    def process_file(self, file_path, filename):
        """
        Processes a single .tar.gz file.
        :param file_path: Full path to the file.
        :param filename: Filename of the file.
        """
        try:
            with tarfile.open(file_path, 'r:gz') as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        file_content = tar.extractfile(member).read()
                        identifier = self.generate_identifier(filename)
                        self.files[identifier][member.name] = io.BytesIO(file_content)
                self.logger.info(f"Processed {filename}")
                self.callback(identifier)  # Notify the caller with the identifier
        except Exception as e:
            self.logger.error(f"Error processing file {filename}: {str(e)}")

    def generate_identifier(self, filename):
        """
        Generates a unique identifier for each file based on filename and timestamp.
        :param filename: The name of the file.
        :return: A unique identifier string.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{filename}_{timestamp}"

    def get_files(self, identifier):
        """
        Returns the file contents for a specific upload identifier.
        :return: Dictionary of file names and their contents.
        """
        return {name: file.getvalue() for name, file in self.files[identifier].items()}
