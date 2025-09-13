from onepassword import OnePassword
from config import OP_SERVICE_ACCOUNT_NAME, OP_SERVICE_ACCOUNT_TOKEN, OP_VAULT_NAME, OP_ITEM_NAME
from ..utils import logger


# Get MFA code from 1Password
async def get_mfa_code_from_1password():
    try:
        logger.debug("Attempting to login to 1Password to get MFA code...")
        onePasswordClient = OnePassword(
            auth=OP_SERVICE_ACCOUNT_TOKEN,
            integration_name=OP_SERVICE_ACCOUNT_NAME,
            integration_version="v1.0.0",
        )
        mfa_code = await onePasswordClient.secrets.resolve("op://" + OP_VAULT_NAME + "/" + OP_ITEM_NAME + "/one-time password?attribute=otp")
        return mfa_code
    except Exception as e:
        logger.error(f"Failed to get MFA code from 1Password: {e}")
        return None
