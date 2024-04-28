import threading
from fs.memoryfs import MemoryFS

class VirtualFileSystem:
    _instance = None
    _lock = threading.Lock()  # Create a lock for thread-safe instance creation

    def __new__(cls, *args, **kwargs):
        # Ensure that instance is created only once
        if cls._instance is None:
            with cls._lock:  # Lock the instance creation process for thread-safety
                if cls._instance is None:  # Double-check locking pattern
                    cls._instance = super(VirtualFileSystem, cls).__new__(cls)
        return cls._instance

    def __init__(self, root='/virtual_root'):
        if not hasattr(self, 'initialized'):  # Avoid reinitializing the instance
            self.memory_fs = MemoryFS()
            self.memory_fs.makedirs(root, recreate=True)
            self.root = root
            self.initialized = True

    def get_fs(self):
        return self.memory_fs
