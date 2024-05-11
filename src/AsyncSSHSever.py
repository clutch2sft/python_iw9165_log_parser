from typing import Optional
import asyncssh

class AsyncSSHServer(asyncssh.SSHServer):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger

    def connection_made(self, conn):
        method_name = self.connection_made.__name__
        super().connection_made(conn)  # Ensure superclass method is called
        self.logger.info(f'{self.__class__.__name__}:{method_name} SSH connection received from {conn.get_extra_info("peername")[0]}')
        if hasattr(conn, 'start_directory'):
            self.logger.info(f"{self.__class__.__name__}:{method_name} Initial directory set to {conn.start_directory}")
        else:
            self.logger.info("{self.__class__.__name__}:{method_name} No start directory set.")

    def connection_lost(self, exc: Optional[Exception]):
        method_name = self.connection_lost.__name__
        if exc:
            self.logger.error(f'{self.__class__.__name__}:{method_name} SSH connection error: {exc}')
        else:
            self.logger.info('{self.__class__.__name__}:{method_name} SSH connection closed.')
        super().connection_lost(exc)

    def begin_auth(self, username: str) -> bool:
        method_name = self.begin_auth.__name__
        self.logger.info(f"{self.__class__.__name__}:{method_name} Authentication started for user {username}")
        return True  # Always require authentication

    def password_auth_supported(self) -> bool:
        method_name = self.password_auth_supported.__name__
        return True

    def validate_password(self, username: str, password: str) -> bool:
        method_name = self.validate_password.__name__
        self.logger.info(f"{self.__class__.__name__}:{method_name} Password validation attempt for user {username}")
        return True  # Accept any password for simplicity
