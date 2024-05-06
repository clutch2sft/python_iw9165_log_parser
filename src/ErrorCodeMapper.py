import re

class ErrorCodeMapper:
    def __init__(self, initial_map=None):
        # Initialize the error_map with an optional initial mapping from a configuration file
        self.error_map = {}
        if initial_map:
            for error_code, regex_pattern in initial_map.items():
                self.add_error_code(error_code, regex_pattern)

    def add_error_code(self, error_code, regex_pattern):
        """ Adds or updates an error code and its corresponding regex pattern to the mapper. """
        self.error_map[error_code] = re.compile(regex_pattern)

    def find_error_code(self, log_entry):
        """ Checks if the log entry matches any of the regex patterns and returns the corresponding error code. """
        for error_code, pattern in self.error_map.items():
            if pattern.search(log_entry):
                return error_code
        return None  # Return None if no error code matches
