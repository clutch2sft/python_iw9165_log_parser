from CIPEventData import CIPEventData
import logging
from threading import Lock
from pydispatch import dispatcher

class CIPEventManager:
    _instance = None
    _lock = Lock()

    def __new__(cls, logger=None):
        with cls._lock:
            if cls._instance is None:
                cls._logger = logger if logger else logging.getLogger('CIPEventManager')
                cls._instance = super(CIPEventManager, cls).__new__(cls)
                cls._instance.events = {}
                cls._instance.id_map = {}
                dispatcher.connect(cls._instance.handle_network_data, signal="NetworkDataReceived", sender=dispatcher.Any)
            return cls._instance

    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    def get_event(self, event_id):
        try:
            return self.id_map[event_id]
        except KeyError:
            print("Event not found with ID:", event_id)
            return None
        
    def add_event(self, ip, dts, txt, erc):
        """
        Creates a new event and stores it in the manager.

        :param ip: IP address related to the event.
        :param dts: The datetime stamp of the event.
        :param txt: Text description of the event.
        :param erc: Error code associated with the event.
        :return: Returns True if the event was added successfully, False otherwise.
        """
        event = CIPEventData(ip, dts, txt, erc)
        if event.id in self.id_map:
            self._logger.debug("Event with this ID already exists.")
            return False
        self.id_map[event.id] = event
        ip_events = self.events.setdefault(ip, {})
        time_events = ip_events.setdefault(event.datetime, [])
        time_events.append(event)
        self._logger.info(f"Event added successfully: {event.id}")
        # Emit an event to notify that a new event has been registered
        dispatcher.send(signal="CIPEventCreated", sender=self, event_id=event.id)
        return True

    def handle_network_data(self, sender, **kw):
        data = kw.get('data')
        ip = data.get('ip')
        dts = data.get('datetime')
        txt = data.get('text')
        erc = data.get('error_code')
        if self.add_event(ip, dts, txt, erc):
            self._logger.info("Network data processed and event created.")

    def add_categorized_logs_to_event(self, event_id, categorized_logs):
        """
        Adds categorized log entries to a single event.

        :param event_id: The ID of the event to which logs are added.
        :param categorized_logs: A dictionary where keys are categories and values are lists of logs.
        """
        if event_id in self.id_map:
            event = self.id_map[event_id]
            for category, logs in categorized_logs.items():
                event.add_categorized_log(category, logs)
            self._logger.debug(f"Added categorized logs to event {event_id}")
            # Optionally emit an updated event signal
            dispatcher.send(signal="EventUpdated", sender=self, event_id=event_id, logs=categorized_logs)
        else:
            self._logger.warning(f"No event found with ID {event_id}")

    def add_categorized_log(self, category, messages):
        """Add multiple messages to a specific log category."""
        if category not in self.categorized_logs:
            self.categorized_logs[category] = []
        self.categorized_logs[category].extend(messages)
