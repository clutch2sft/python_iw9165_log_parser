from datetime import datetime

class CIPEventData:
    def __init__(self, ip, dts, txt, erc):
        self.ip = ip
        self.datetime = datetime.fromisoformat(dts)
        self.txt = txt
        self.erc = erc
        self.id = f"{ip}_{dts}"
        self.log_messages = []  # List to store general log messages
        self.categorized_logs = {}  # Dictionary to store categorized log messages

    def add_log_message(self, message):
        """Adds a log message to the general log list."""
        self.log_messages.append(message)

    def add_categorized_log(self, category, message):
        """
        Adds a log message under a specific category.

        :param category: The category under which the log should be stored (e.g., 'basic', 'details').
        :param message: The log message to store.
        """
        if category not in self.categorized_logs:
            self.categorized_logs[category] = []
        self.categorized_logs[category].append(message)

    def get_categorized_logs(self, category):
        """
        Returns all log messages for a specific category.

        :param category: The category of logs to retrieve.
        :return: A list of log messages for the given category.
        """
        return self.categorized_logs.get(category, [])
