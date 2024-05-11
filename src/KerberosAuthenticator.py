import asyncio
import kerberos
import logging

class KerberosAuthenticator:
    def __init__(self, service, logger=None):
        self.service = service
        self.logger = logger or logging.getLogger(__name__)

    async def authenticate(self, username, password):
        loop = asyncio.get_event_loop()
        method_name = self.__class__.__name__ + '.authenticate'
        try:
            result, context = await loop.run_in_executor(None, kerberos.authGSSClientInit, self.service)
            await loop.run_in_executor(None, kerberos.authGSSClientStep, context, "")
            final_result = await loop.run_in_executor(None, kerberos.authGSSClientStep, context, "", username, password)
            if kerberos.authGSSClientResponse(context):
                self.logger.info(f"{method_name}: Authentication successful for user {username}")
                return True
            else:
                self.logger.warning(f"{method_name}: Invalid credentials for user {username}")
                return False
        except kerberos.GSSError as e:
            self.logger.error(f"{method_name}: Kerberos authentication failed for user {username} with error: {e}")
            return False
        finally:
            if 'context' in locals():
                kerberos.authGSSClientClean(context)
                self.logger.debug(f"{method_name}: Cleaned up Kerberos context for user {username}")



# The KerberosAuthenticator can now use this logger.
# authenticator = KerberosAuthenticator('http@your.service.com', logger=logger)
