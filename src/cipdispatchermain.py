"""
This file is the main events based program.
"""

import asyncio
import logging
import signal
#from pydispatch.dispatch import Dispatcher
from pydispatch import dispatcher
from CIPEventManager import CIPEventManager  # Ensure these are correctly imported
from CiscoDeviceManager import CiscoDeviceManager
from CIPNetworkListener import CIPNetworkListener
from ConfigurationLoader import ConfigLoader
from DeviceLogger import DeviceLogger
from VirtualFileSystem import VirtualFileSystem
from AsyncMainSFTPServer import AsyncMainSFTPServer
from TarFileExtractor import TarFileExtractor
from IwEventParser import IwEventParser
from SyslogSender import SyslogSender

def logger_setup(config):
    # Load the configuration settings
    output_dir = config['output_dir']
    log_format = config['log_format']
    console_level = getattr(logging, config.get('console_level', 'INFO')) if config.get('console_level', None) else None
    # Configure root logger
    logging.basicConfig(level=logging.DEBUG, format=log_format)
    # Set up specific logger for the SFTP server
    my_logger = DeviceLogger.get_logger("asyncsftpserver", output_dir, console_level=console_level, format=log_format, external_handler=False)
    return my_logger

def setup_asyncssh_logger(config):
    output_dir = config['output_dir']
    log_format = config['log_format']
    asyncssh_debug_level = getattr(logging, config.get('asnyncssh_level', 'INFO')) if config.get('asnyncssh_level', None) else None
    logger = logging.getLogger('asyncssh')
    # Define the file handler with a specific log file
    file_handler = logging.FileHandler(output_dir + '/asyncssh.log')
    file_handler.setLevel(asyncssh_debug_level)  # Adjust the level as needed
    # Create a formatter and set it on the file handler
    #formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter(log_format)
    file_handler.setFormatter(formatter)
    # Add the file handler to the logger
    logger.addHandler(file_handler)
    # Optionally set the logging level on the logger if you want it to be different from the global level
    logger.setLevel(asyncssh_debug_level)

async def start_sftp_server(fs, logger, config):
    sftp_server = AsyncMainSFTPServer(None, None, fs, logger, config)
    server = await sftp_server.start_sftp_server()
    return server

async def graceful_shutdown(loop, signal=None):
    """Gracefully shutdown the server and asyncio loop."""
    if signal:
        print(f"Received exit signal {signal.name}, gracefully shutting down...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    print(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()
    print("Shutdown complete")

def handle_exit_signal(signal, loop):
    asyncio.create_task(graceful_shutdown(loop, signal))

async def main():
    config_loader = ConfigLoader()
    config = config_loader.get_configuration()
    main_logger = logger_setup(config)
    setup_asyncssh_logger(config)
    device_manager_config = {
        'device_type': 'cisco_ios',
        'username': 'admin',
        'password': 'pass',
        'secret': 'secret',
        'port': 22
    }    # Initialize components
    # Setup other components as before...
    vfs = VirtualFileSystem()
    #We listen here for a CIPEvent and let event_manager handle that.
    event_manager = CIPEventManager(main_logger)

    dispatcher.connect(event_manager.handle_network_data, signal="NetworkDataReceived", sender=dispatcher.Any)
    #event_manager emits the CIP event created when it completes its work
    device_manager = CiscoDeviceManager(device_manager_config, logger=main_logger)
    dispatcher.connect(device_manager.connect_and_retrieve_logs, signal="CIPEventCreated", sender=dispatcher.Any)
    #Now device_manager will get the sftp file flowing so we need something to listen for that here:
    #Problem is that now we lose our event.id because it was in the flow but to fix that we
    #Make sure the filename coming in from the device is eventid.tar.gz
    extractor = TarFileExtractor(main_logger, vfs.get_fs())
    dispatcher.connect(extractor.handle_file_received, signal="FileReceived", sender=dispatcher.Any)
    # Initialize and register the IwEventParser
    event_parser = IwEventParser(vfs.get_fs(), main_logger)
    dispatcher.connect(event_parser.handle_extraction_completed, signal="ExtractionCompleted", sender=dispatcher.Any)
    # Deal with the log data which is to a) send to syslog server, b) do analysis of it for sending back to plc
    syslog_sndr = SyslogSender(main_logger, '1.1.1.1', 514) # Configure these details
    dispatcher.connect(syslog_sndr.handle_log_processing_completed, signal="LogProcessingCompleted", sender=dispatcher.Any)
    loop = asyncio.get_running_loop()
    # Attach signal handlers
    for signame in {'SIGINT', 'SIGTERM'}:
        loop.add_signal_handler(
            getattr(signal, signame),
            handle_exit_signal,
            getattr(signal, signame),
            loop
        )


    network_listener = CIPNetworkListener(host='0.0.0.0', port=9999, use_udp=True, logger=main_logger)
    await network_listener.start_server()

    # Replace the old SFTP server start method with the new async one
    sftp_server = await start_sftp_server(vfs.get_fs(), main_logger, config)

    # Maintain service operation
    try:
        await asyncio.Future()  # Run forever until a KeyboardInterrupt is caught

    except asyncio.CancelledError:
        print("Main task was cancelled. This is expected during a graceful shutdown.")

    except KeyboardInterrupt:
        print("Received exit, stopping servers...")
        sftp_server.close()
        await sftp_server.wait_closed()
        await network_listener.shutdown()
    finally:
        # Ensure all cleanup routines are called here
        print("Cleanup can be done here.")



if __name__ == '__main__':

    asyncio.run(main())
