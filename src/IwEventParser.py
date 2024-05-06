from datetime import datetime, timedelta
from pydispatch import dispatcher
from CIPEventManager import CIPEventManager
import os

class IwEventParser:
    def __init__(self, fs, logger, event_window = 2):
        """
        Initializes the IwEventParser with a virtual filesystem and a logger.
        """
        self.fs = fs
        self.logger = logger
        self.event_window = event_window
        dispatcher.connect(self.handle_extraction_completed, signal="ExtractionCompleted", sender=dispatcher.Any)

    def handle_extraction_completed(self, sender, **kwargs):
        manager = CIPEventManager.get_instance()  # Assuming there's a get_instance class method.
        directory = kwargs['directory']
        extracted_items = kwargs['extracted_items']
        event_id = kwargs['event_id']
        self.logger.info(f"Handling extracted data in directory: {directory} with items: {extracted_items}")

        # Assume some way to determine the base timestamp and window, possibly from filename or metadata
        base_timestamp = '01/01/2020 12:00:00.000'

        log_results = {}
        # Process each item that was extracted
        for filepath in extracted_items:
            filename = os.path.basename(filepath)
            self.set_filename(filepath)  # Set the file to be processed
            if self.is_file_non_empty():
                filtered_logs = self.filter_events_by_time_window(base_timestamp, self.event_window)
                if filtered_logs:
                    # Store logs keyed by filename without the extension
                    file_key = os.path.splitext(filename)[0]
                    log_results[file_key] = filtered_logs
        
        # If there are any logs to add, add them to the event.
        if log_results:
            manager.add_categorized_logs_to_event(event_id, log_results)

        # Optionally emit an event if other systems need to react to the completion of log processing
        dispatcher.send(signal="LogProcessingCompleted", sender=self, event_id=event_id)

    def _check_file_content(self):
        """
        Checks if the file is not zero bytes by accessing the 'details' namespace.
        """
        try:
            info = self.fs.getinfo(self.filename, namespaces=['details'])
            return info.get('details', 'size', 0) > 0
        except Exception as e:
            self.logger.error(f"Error checking content for {self.filename}: {str(e)}")
            return False

    def read_ten_lines(self):
        """
        Reads the first ten lines of the file and logs them.
        """
        try:
            with self.fs.open(self.filename, 'r') as file:
                for i in range(10):
                    line = file.readline()
                    if not line:
                        break  # Exit loop if no more lines
                    self.logger.info(f"Line {i + 1}: {line.strip()}")
        except Exception as e:
            self.logger.error(f"Error reading from {self.filename}: {str(e)}")

    def set_filename(self, new_filename):
        """
        Sets a new filename for subsequent parsing operations and checks its content.
        
        :param new_filename: The new filename to set.
        """
        self.filename = new_filename
        self.file_has_content = self._check_file_content()

    def is_file_non_empty(self):
        """
        Returns True if the file is not zero bytes, otherwise False.
        """
        return self.file_has_content

    def filter_events_by_time_window(self, base_timestamp, time_window_seconds):
        """
        Filters log entries that are within a specified time window around a given timestamp.
        
        :param base_timestamp: The central timestamp in the format 'MM/DD/YYYY HH:MM:SS'.
        :param time_window_seconds: The time window in seconds around the base timestamp.
        :return: A list of log entries within the time window.
        """
        base_datetime = datetime.strptime(base_timestamp, "%m/%d/%Y %H:%M:%S.%f")
        time_delta = timedelta(seconds=time_window_seconds)
        
        start_window = base_datetime - time_delta
        end_window = base_datetime + time_delta
        
        events_within_window = []

        try:
            with self.fs.open(self.filename, 'r') as file:
                for line in file:
                    if line.startswith('['):
                        try:
                            # Remove the asterisk and parse the datetime from the log line
                            end_bracket = line.find(']')
                            date_str = line[1:end_bracket].replace('*', '').strip()
                            log_datetime = datetime.strptime(date_str, "%m/%d/%Y %H:%M:%S.%f")
                            
                            if log_datetime < start_window:
                                continue  # Skip this line if it's before the start of the window
                            if log_datetime > end_window:
                                break  # Stop processing if past the end of the window
                            
                            events_within_window.append(line.strip())
                        except ValueError:
                            self.logger.error(f"Error parsing date from line: {line.strip()}")
                            continue
        except Exception as e:
            self.logger.error(f"Error reading from {self.filename}: {str(e)}")
        
        return events_within_window
    
    def cleanup_directory(self, directory):
        """
        Deletes the specified directory and all its contents from the virtual filesystem.

        :param directory: The directory to be deleted.
        """
        try:
            self.fs.removetree(directory)  # Recursively remove the directory and its contents
            self.logger.info(f"Successfully cleaned up directory: {directory}")
        except Exception as e:
            self.logger.error(f"Failed to clean up directory {directory}: {str(e)}")
