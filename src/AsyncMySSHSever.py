from typing import Optional
import asyncssh

class AsyncMySSHServer(asyncssh.SSHServer):
    def __init__(self, logger):
        super().__init__()
        self.logger = logger

    def connection_made(self, conn):
        super().connection_made(conn)  # Ensure superclass method is called
        self.logger.info(f'SSH connection received from {conn.get_extra_info("peername")[0]}')
        if hasattr(conn, 'start_directory'):
            self.logger.info(f"Initial directory set to {conn.start_directory}")
        else:
            self.logger.info("No start directory set.")

    def connection_lost(self, exc: Optional[Exception]):
        if exc:
            self.logger.error(f'SSH connection error: {exc}')
        else:
            self.logger.info('SSH connection closed.')
        super().connection_lost(exc)

    def begin_auth(self, username: str) -> bool:
        self.logger.info(f"Authentication started for user {username}")
        return True  # Always require authentication

    def password_auth_supported(self) -> bool:
        return True

    def validate_password(self, username: str, password: str) -> bool:
        self.logger.info(f"Password validation attempt for user {username}")
        return True  # Accept any password for simplicity
