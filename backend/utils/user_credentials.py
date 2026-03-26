"""
User Kite credentials storage and retrieval
Handles encryption/decryption of API keys and access tokens
"""
import logging
from utils.supabase_client import supabase
from utils.auth import encrypt_credential, decrypt_credential

logger = logging.getLogger("user_credentials")

# ============ DATABASE OPERATIONS ============

def save_user_credentials(user_id: int, api_key: str, access_token: str) -> dict:
    """
    Save encrypted user Kite credentials to database
    
    Args:
        user_id: User's ID
        api_key: Zerodha API key
        access_token: Zerodha access token
    
    Returns:
        dict: {"status": "ok", "user_id": user_id} or error
    """
    try:
        # Encrypt sensitive data
        encrypted_api_key = encrypt_credential(api_key)
        encrypted_access_token = encrypt_credential(access_token)
        
        # Check if credentials already exist
        existing = supabase.table('user_kite_credentials').select('*').eq('user_id', user_id).execute()
        
        if existing.data:
            # Update existing
            result = supabase.table('user_kite_credentials').update({
                'api_key': encrypted_api_key,
                'access_token': encrypted_access_token
            }).eq('user_id', user_id).execute()
            logger.info(f"Updated Kite credentials for user {user_id}")
        else:
            # Insert new
            result = supabase.table('user_kite_credentials').insert({
                'user_id': user_id,
                'api_key': encrypted_api_key,
                'access_token': encrypted_access_token
            }).execute()
            logger.info(f"Saved Kite credentials for user {user_id}")
        
        return {"status": "ok", "user_id": user_id}
    except Exception as e:
        logger.error(f"Error saving credentials for user {user_id}: {e}")
        raise


def get_user_credentials(user_id: int) -> dict:
    """
    Retrieve and decrypt user Kite credentials
    
    Args:
        user_id: User's ID
    
    Returns:
        dict: {"api_key", "access_token"} or None if not found
    """
    try:
        result = supabase.table('user_kite_credentials').select('*').eq('user_id', user_id).execute()
        
        if not result.data:
            logger.warning(f"No credentials found for user {user_id}")
            return None
        
        cred = result.data[0]
        
        return {
            'api_key': decrypt_credential(cred['api_key']),
            'access_token': decrypt_credential(cred['access_token'])
        }
    except Exception as e:
        logger.error(f"Error retrieving credentials for user {user_id}: {e}")
        raise


def user_has_credentials(user_id: int) -> bool:
    """Check if user has saved Kite credentials"""
    try:
        result = supabase.table('user_kite_credentials').select('user_id').eq('user_id', user_id).execute()
        return len(result.data) > 0
    except Exception as e:
        logger.error(f"Error checking credentials for user {user_id}: {e}")
        return False


def delete_user_credentials(user_id: int) -> bool:
    """Delete user's saved Kite credentials"""
    try:
        result = supabase.table('user_kite_credentials').delete().eq('user_id', user_id).execute()
        logger.info(f"Deleted Kite credentials for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting credentials for user {user_id}: {e}")
        return False
