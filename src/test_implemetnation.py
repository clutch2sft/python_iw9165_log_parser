"""
This file was used pre-event driven system
IE: When I was using a million and one callbacks.
"""

import logging, threading
from DeviceLogger import DeviceLogger
from ConfigurationLoader import ConfigLoader
from MainSFTPServer import MainSFTPServer
from VirtualFileSystem import VirtualFileSystem
from TarFileExtractor import TarFileExtractor
from IwEventParser import IwEventParser
from SyslogSender import SyslogSender

def logger_setup(set_plogger = False):
    # Load the configuration settings
    config_loader = ConfigLoader()
    config = config_loader.get_configuration()
    output_dir = config['output_dir']
    log_format = config['log_format']
    console_level = getattr(logging, config.get('console_level', 'INFO')) if config.get('console_level', None) else None
   # Configure root logger
    logging.basicConfig(level=logging.DEBUG, format=log_format)
    # Set up specific logger for the SFTP server
    my_logger = DeviceLogger.get_logger("sftpserver", output_dir, console_level=console_level, format=log_format, external_handler=False)
    if set_plogger:
        plogger_setup()
    return my_logger

def plogger_setup():
    # Set Paramiko logger to debug
    paramiko_logger = logging.getLogger('paramiko')
    paramiko_logger.setLevel(logging.DEBUG)

def file_received_callback(file_path):
    frc_logger = logger_setup()
    frc_logger.error(f"CALLBACK: New file received: {file_path}")
    # Additional processing can be performed here

def handle_file_received(full_path):
    """
    This function will be called after a file is uploaded.
    It starts a new thread to handle the extraction and processing of the file.
    """
    hfr_logger = logger_setup()
    hfr_logger.error(f"CALLBACK: New file received: {full_path} starting process tar file thread.")
    thread = threading.Thread(target=process_tar_file, args=(full_path,))
    thread.start()

def process_tar_file(full_path):
    """
    Extracts the tar file and processes its contents.
    """
    ptf_logger = logger_setup()
    ptf_logger.error(f"Extractor running on {full_path}.")
   # Start thread
    extraction_thread = threading.Thread(target=run_extraction, args=(full_path, ptf_logger,))
    extraction_thread.start()

def run_extraction(extracted_dir, re_logger):
    try:
        vfs = VirtualFileSystem()
        extractor = TarFileExtractor(vfs.get_fs(), extracted_dir, process_extracted_files, re_logger)
        extractor.extract_files()
        re_logger.info(f"Completed extraction for {extracted_dir}.")
    except Exception as e:
        re_logger.error(f"Error during extraction of {extracted_dir}: {str(e)}")

def process_extracted_files(extracted_dir, extracted_items):
    vfs = VirtualFileSystem()  # Assuming an existing VirtualFileSystem instance
    pef_logger = logger_setup()
    pef_logger.info(f"Extracted Files are in {extracted_dir}")

    def worker(vfs, items):
        parser = IwEventParser(vfs.get_fs(), items[0], pef_logger)
        slogger = SyslogSender(pef_logger, '172.16.5.40', 514)
        for item in items:
            pef_logger.info(f"Processing Extracted File: {item}")
            parser.set_filename(item)
            if parser.is_file_non_empty():
                parser.read_ten_lines()
                interesting_events = get_time_window(item, parser, 1)
                slogger.send_events(interesting_events, '120.247.219.103')
                for event in interesting_events:
                    pef_logger.info(f"Interesting:{event}")
            else:
                pef_logger.info(f"The file {item} is empty.")
        parser.cleanup_directory(extracted_dir)
    
    # Start the thread
    thread = threading.Thread(target=worker, args=(vfs, extracted_items,))
    thread.start()

def get_time_window(fulname, parser, twin):
    dts_str = "02/20/2024 15:18:38.695639"
    return parser.filter_events_by_time_window(dts_str, twin)



def main():

    main_logger = logger_setup(True)

    # Initialize the VirtualFileSystem  
    vfs = VirtualFileSystem()

    # Create an instance of MainSFTPServer
    sftp_server = MainSFTPServer(vfs.get_fs(), main_logger, file_received_callback=handle_file_received)

    # Start the SFTP server
    try:
        sftp_server.start_server()
    except Exception as e:
        main_logger.error(f"Failed to start the SFTP server: {str(e)}")
    finally:
        sftp_server.stop_server()

if __name__ == "__main__":
    main()
