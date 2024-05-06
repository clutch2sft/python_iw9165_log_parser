"""
This file was only used during the building of the aysncsftp server
it is kept around in order to allow for future standalone testing
"""
import asyncio
import logging
from AsyncMainSFTPServer import AsyncMainSFTPServer
from VirtualFileSystem import VirtualFileSystem
from DeviceLogger import DeviceLogger
from ConfigurationLoader import ConfigLoader

def logger_setup(set_plogger=False):
    # Load the configuration settings
    config_loader = ConfigLoader()
    config = config_loader.get_configuration()
    output_dir = config['output_dir']
    log_format = config['log_format']
    console_level = getattr(logging, config.get('console_level', 'INFO'), logging.INFO)

    # Configure root logger
    logging.basicConfig(level=logging.DEBUG, format=log_format)

    # Set up specific logger for the SFTP server
    my_logger = DeviceLogger.get_logger("sftpserver", output_dir, console_level=console_level, format=log_format, external_handler=False)

    return my_logger

def setup_asyncssh_logger():
    logger = logging.getLogger('asyncssh')
    
    # Define the file handler with a specific log file
    file_handler = logging.FileHandler('/home/greggc/python_iw9165_log_parser/logs/asyncssh.log')
    file_handler.setLevel(logging.DEBUG)  # Adjust the level as needed

    # Create a formatter and set it on the file handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger
    logger.addHandler(file_handler)

    # Optionally set the logging level on the logger if you want it to be different from the global level
    logger.setLevel(logging.DEBUG)

async def start_sftp_server(fs, logger, config):
    sftp_server = AsyncMainSFTPServer(None, None, fs, logger, config)
    server = await sftp_server.start_sftp_server()
    return server



def main():
    config_loader = ConfigLoader()
    config = config_loader.get_configuration()
    # Setup virtual file system
    vfs = VirtualFileSystem()
    fs = vfs.get_fs()

    # Setup logger
    logger = logger_setup()
    setup_asyncssh_logger()
    
    # Run the async SFTP server
    loop = asyncio.get_event_loop()
    server = None  # Initialize server to None to handle exceptions properly
    
    try:
        server = loop.run_until_complete(start_sftp_server(fs, logger, config))
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server.")
        if server:
            server.close()
            loop.run_until_complete(server.wait_closed())
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        loop.close()
        logger.info("Server loop closed.")

if __name__ == '__main__':
    main()

