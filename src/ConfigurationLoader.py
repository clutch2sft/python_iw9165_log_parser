import json, sys, shutil
from pathlib import Path

class ConfigLoader:
    _instance = None  # Class attribute to store the singleton instance

    def __new__(cls, filepath=None):
        """ Override the __new__ method to ensure only one instance exists. """
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            # Set default path if none provided
            if filepath is None:
                if getattr(sys, 'frozen', False):
                    # If the application is frozen using PyInstaller
                    base_path = Path(sys.executable).resolve().parent
                else:
                    # Normal execution path
                    base_path = Path(__file__).resolve().parent.parent
                filepath = base_path / 'config' / 'config.json'
            cls._instance.config = cls._instance.load_config(filepath)
        return cls._instance

    def load_config(self, filepath):
        """ Load the JSON config file and clean it. """
        if not filepath.exists():
            print(f"Configuration file not found at {filepath}.")
            try:
                sample_path = filepath.parent / 'config.json.sample'
                if sample_path.exists():
                    shutil.copy(sample_path, filepath)
                    print(f"Sample configuration file copied to {filepath}. Please edit this file and restart the application.")
                else:
                    print("No sample configuration file found. Please ensure a config.json file exists.")
            except Exception as e:
                print(f"Failed to copy sample configuration file: {str(e)}")
            sys.exit(1)
        try:
            with open(filepath, 'r') as file:
                config = json.load(file)
            # Clean out any comments from the configuration
            self.remove_comments(config)
            return config
        except FileNotFoundError:
            raise Exception(f"The configuration file {filepath} was not found.")
        except json.JSONDecodeError:
            raise Exception("Error decoding the configuration file. Ensure it is valid JSON.")

    def remove_comments(self, config):
        """ Recursively remove __comments__ keys from the configuration dictionary. """
        if isinstance(config, dict):
            config.pop('__comments__', None)
            for key, value in list(config.items()):
                config[key] = self.remove_comments(value)
        elif isinstance(config, list):
            return [self.remove_comments(item) for item in config]
        return config

    def get_devices(self):
        """ Retrieve the list of devices from the configuration. """
        return self.config.get('devices', [])

    def get_configuration(self):
        """ Retrieve the general configuration. """
        return self.config.get('configuration', {})
    
    def get_terminal_output(self):
        """ Retrieve the terminal output colorizer configuration. """
        return self.config.get('terminal_output', {})