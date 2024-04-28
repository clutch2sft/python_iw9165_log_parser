import paramiko
from getpass import getpass

def print_progress(transferred, total):
    print(f"Transferred: {transferred} out of {total} bytes ({100 * transferred // total}%)")

def sftp_upload(host, port, file_to_upload, destination_path):
    transport = paramiko.Transport((host, port))
    try:
        # Connect using specified credentials and disable GSS-API
        transport.connect(
            username="user", 
            password="pass", 
            gss_auth=False, 
            gss_kex=False
        )
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.put(file_to_upload, destination_path, callback=print_progress)
        print(f"File {file_to_upload} uploaded to {destination_path}")
    except paramiko.AuthenticationException:
        print("Authentication failed, please check your credentials")
    except Exception as e:
        print(f"Failed to upload file: {str(e)}")
    finally:
        if sftp:
            sftp.close()
        transport.close()

if __name__ == "__main__":
    host = 'localhost'  # Server hostname or IP address
    port = 2222  # Port number where your SFTP server is listening
    file_to_upload = '/media/greggc/ADATA SD600/pcaps/download_4-3-24/evt_tar_files/evtlog103_20240402004501.tar.gz'
    destination_path = '/evtlog103_20240402004501.tar.gz'
    
    sftp_upload(host, port, file_to_upload, destination_path)
