import threading
import paramiko
import socket
import sys
import logging
import traceback
from MemorySftp import MemorySFTPServer, SFTPHandler
from DeviceLogger import DeviceLogger
from ConfigurationLoader import ConfigLoader

def notification_callback(identifier, server_instance):
    file_contents = server_instance.get_files(identifier)
    if file_contents:
        # Printing the contents of the first file found
        first_file_name, file_content = next(iter(file_contents.items()))
        print(f"Content of the first file ({first_file_name}): {file_content.getvalue().decode()}")
    else:
        print(f"No files found for identifier {identifier}")

def start_sftp_server(port=2222):
    # Set up logger
    logging.basicConfig(level=logging.DEBUG)
    config_loader = ConfigLoader()
    config = config_loader.get_configuration()
    output_dir = config['output_dir']
    log_format = config['log_format']
    console_level = getattr(logging, config.get('console_level', 'INFO')) if config.get('console_level', None) else None
    my_logger = DeviceLogger.get_logger("sftpserver", output_dir, console_level=console_level, format=log_format, external_handler=False)
    host_key = paramiko.RSAKey.generate(1024)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    sock.bind(("localhost", port))
    sock.listen(10)

    print(f"SFTP server running on port {port}...")



    while True:
        client, addr = None, None
        try:
            client, addr = sock.accept()
            print(f"Connected to {addr}")
            transport = paramiko.Transport(client)
            transport.add_server_key(host_key)

            # Set the SFTP handler
            transport.set_subsystem_handler(
                'sftp', MemorySFTPServer, logger=my_logger
            )

            server = MemorySFTPServer(transport, callback=notification_callback)
            transport.start_server(server=server)

            while transport.is_active():
                pass  # This maintains the connection; consider a sleep here to avoid CPU spin

        except Exception as e:
            print(f"Exception occurred: {e}")
            traceback.print_exc()  # Print detailed traceback to understand where and why the exception occurred

        finally:
            if client is not None:
                client.close()  # Ensure the socket to the client is closed properly
            if addr:
                print(f"Connection closed for {addr}")


if __name__ == "__main__":
    thread = threading.Thread(target=start_sftp_server, daemon=True)
    thread.start()
    input("Press Enter to stop the server...\n")
    thread.join()