import asyncio
import asyncssh
import sys

class MySSHServer(asyncssh.SSHServer):
    def __init__(self):
        super().__init__()

    def password_auth_supported(self):
        return True

    def validate_password(self, username, password):
        # Implement your password validation logic here
        #return password == 'secret'  # Example: only 'secret' is a valid password
        return True

    def session_requested(self):
        return False  # Do not allow shell access

    def sftp_requested(self):
        return True  # Allow SFTP sessions

async def start_ssh_sftp_server():
    await asyncssh.listen(
        '',  # Listen on all network interfaces
        8022,  # Port number
        server_host_keys=['/home/greggc/test_sftp_server_keyfile.key'],  # Path to server key
        sftp_factory=asyncssh.SFTPServer,  # Use default SFTP server
        process_factory=None,  # No shell or command execution allowed
        session_factory=None,  # No separate sessions allowed
        server_factory=lambda: MySSHServer()  # Factory to create instances of your SSHServer
    )
    print("SFTP server started on port 8022")

async def main():
    try:
        await start_ssh_sftp_server()
        await asyncio.Future()  # Keep the server running indefinitely
    except (OSError, asyncssh.Error) as exc:
        sys.exit(f'Error starting SFTP server: {str(exc)}')

if __name__ == '__main__':
    asyncio.run(main())
