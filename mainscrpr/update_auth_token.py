"""
Script to update the auth_token in TrendyolAPIConfig.

This script updates the auth_token field in the active TrendyolAPIConfig
with the provided token or generates a new one from the API key and secret.

Run this script with: python manage.py shell < update_auth_token.py
"""

import logging
import base64
from trendyol.models import TrendyolAPIConfig

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_auth_token():
    """Update the auth_token in the active TrendyolAPIConfig."""
    logger.info("Updating auth_token in TrendyolAPIConfig")
    
    try:
        # Get the active config
        config = TrendyolAPIConfig.objects.filter(is_active=True).first()
        
        if not config:
            logger.error("No active TrendyolAPIConfig found")
            return False
        
        # Use the provided token or generate a new one
        auth_token = "cVNvaEtrTEtQV3dEZVNLand6OFI6eVlGM1ljbDlCNlZqczc3cTNNaEU="
        
        if not auth_token:
            # Generate auth token from API key and secret
            auth_string = f"{config.api_key}:{config.api_secret}"
            auth_token = base64.b64encode(auth_string.encode()).decode('utf-8')
            logger.info(f"Generated auth token from API key and secret")
        
        # Update the config
        config.auth_token = auth_token
        config.save()
        
        logger.info(f"Updated auth_token in TrendyolAPIConfig (ID: {config.id})")
        return True
    except Exception as e:
        logger.error(f"Error updating auth_token: {str(e)}")
        return False

def main():
    """Main function."""
    logger.info("Starting auth_token update...")
    
    update_success = update_auth_token()
    
    if update_success:
        logger.info("auth_token update completed successfully")
    else:
        logger.error("auth_token update failed")
    
    logger.info("auth_token update process completed")

if __name__ == "__main__":
    main()
else:
    # When imported from Django shell
    main()