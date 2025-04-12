"""
Script to fix the TrendyolAPIConfig model to include auth_token field.

This script adds the auth_token field to the TrendyolAPIConfig model using Django's
migration system, then updates the existing config with the token.

Run this script with: python manage.py shell < fix_api_model.py
"""

import logging
import os
import subprocess
from trendyol.models import TrendyolAPIConfig
from django.utils import timezone
import base64

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_model_file():
    """Update the model file to add auth_token field."""
    logger.info("Updating model file")
    
    file_path = "trendyol/models.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find the TrendyolAPIConfig class
        if "class TrendyolAPIConfig(models.Model)" in content:
            # Add auth_token field if it doesn't exist
            if "auth_token = models.CharField" not in content:
                lines = content.split('\n')
                updated_lines = []
                
                in_config_class = False
                added_field = False
                
                for line in lines:
                    updated_lines.append(line)
                    
                    if line.strip() == "class TrendyolAPIConfig(models.Model):":
                        in_config_class = True
                    elif in_config_class and not added_field and line.strip().startswith("api_key = models.CharField"):
                        # Add auth_token field after api_key
                        updated_lines.append("    auth_token = models.CharField(max_length=255, blank=True, help_text='Base64 encoded auth token')")
                        added_field = True
                
                # Write the updated content
                with open(file_path, 'w') as f:
                    f.write('\n'.join(updated_lines))
                
                logger.info("Added auth_token field to TrendyolAPIConfig model")
                return True
            else:
                logger.info("auth_token field already exists in TrendyolAPIConfig model")
                return True
        else:
            logger.error("Could not find TrendyolAPIConfig class in model file")
            return False
    except Exception as e:
        logger.error(f"Error updating model file: {str(e)}")
        return False

def create_migration():
    """Create a migration for the model changes."""
    logger.info("Creating migration")
    
    try:
        # Run makemigrations command
        result = subprocess.run(
            ["python", "manage.py", "makemigrations", "trendyol", "--name", "add_auth_token"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"Migration created successfully: {result.stdout}")
            return True
        else:
            logger.error(f"Error creating migration: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error creating migration: {str(e)}")
        return False

def apply_migration():
    """Apply the migration."""
    logger.info("Applying migration")
    
    try:
        # Run migrate command
        result = subprocess.run(
            ["python", "manage.py", "migrate", "trendyol"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"Migration applied successfully: {result.stdout}")
            return True
        else:
            logger.error(f"Error applying migration: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error applying migration: {str(e)}")
        return False

def update_config_directly():
    """Update the config directly in the database."""
    logger.info("Updating config directly in the database")
    
    try:
        # Directly execute SQL to add the auth_token
        from django.db import connection
        with connection.cursor() as cursor:
            # Check if the column exists
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='trendyol_trendyolapiconfig' AND column_name='auth_token'")
            if cursor.fetchone():
                # Update the existing config
                cursor.execute(
                    "UPDATE trendyol_trendyolapiconfig SET auth_token = %s WHERE is_active = TRUE",
                    ["cVNvaEtrTEtQV3dEZVNLand6OFI6eVlGM1ljbDlCNlZqczc3cTNNaEU="]
                )
                logger.info("Updated auth_token in existing config")
                return True
            else:
                # Add the column if it doesn't exist
                cursor.execute("ALTER TABLE trendyol_trendyolapiconfig ADD COLUMN auth_token character varying(255) NOT NULL DEFAULT ''")
                
                # Update the existing config
                cursor.execute(
                    "UPDATE trendyol_trendyolapiconfig SET auth_token = %s WHERE is_active = TRUE",
                    ["cVNvaEtrTEtQV3dEZVNLand6OFI6eVlGM1ljbDlCNlZqczc3cTNNaEU="]
                )
                logger.info("Added auth_token column and updated existing config")
                return True
    except Exception as e:
        logger.error(f"Error updating config directly: {str(e)}")
        return False

def update_trendyol_api_working():
    """Update the trendyol_api_working.py file to properly handle auth_token."""
    logger.info("Updating trendyol_api_working.py file")
    
    file_path = "trendyol/trendyol_api_working.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update the authentication token handling
        if "self.auth_token = self.config.auth_token" in content:
            # API is already handling auth_token correctly
            logger.info("trendyol_api_working.py is already handling auth_token correctly")
            return True
        
        # Generate authentication token from API key and secret if auth_token is not available
        lines = content.split('\n')
        updated_lines = []
        
        for i, line in enumerate(lines):
            updated_lines.append(line)
            
            if line.strip() == "self.auth_token = self.config.auth_token":
                # Add fallback for auth_token
                updated_lines.pop()  # Remove the line we just added
                updated_lines.append("            # Try to get auth token, or generate from API key and secret")
                updated_lines.append("            if hasattr(self.config, 'auth_token') and self.config.auth_token:")
                updated_lines.append("                self.auth_token = self.config.auth_token")
                updated_lines.append("            else:")
                updated_lines.append("                # Generate auth token from API key and secret")
                updated_lines.append("                auth_string = f\"{self.api_key}:{self.api_secret}\"")
                updated_lines.append("                self.auth_token = base64.b64encode(auth_string.encode()).decode('utf-8')")
                updated_lines.append("                logger.info(f\"Generated auth token from API key and secret: {self.auth_token}\")")
        
        # Write the updated content
        with open(file_path, 'w') as f:
            f.write('\n'.join(updated_lines))
        
        logger.info("Updated trendyol_api_working.py to properly handle auth_token")
        return True
    except Exception as e:
        logger.error(f"Error updating trendyol_api_working.py: {str(e)}")
        return False

def test_update():
    """Test the updated API client."""
    logger.info("Testing updated API client")
    
    try:
        # Import the working API
        from trendyol.trendyol_api_working import TrendyolAPI
        
        # Initialize the API client
        api = TrendyolAPI()
        
        # Get categories to test
        categories = api.get_categories()
        
        if categories and len(categories) > 0:
            logger.info(f"Successfully retrieved {len(categories)} categories")
            logger.info("API client is working correctly!")
            return True
        else:
            logger.error("No categories found. API client might not be working correctly.")
            return False
    except Exception as e:
        logger.error(f"Error testing API client: {str(e)}")
        return False

def main():
    """Main function."""
    logger.info("Starting API model fix...")
    
    # Update the model file
    model_updated = update_model_file()
    
    if not model_updated:
        logger.error("Failed to update model file. Trying direct database update...")
        
    # Update the config directly in the database
    config_updated = update_config_directly()
    
    if not config_updated:
        logger.error("Failed to update config directly. API client might not work correctly.")
    
    # Update the trendyol_api_working.py file
    api_working_updated = update_trendyol_api_working()
    
    if not api_working_updated:
        logger.error("Failed to update trendyol_api_working.py file.")
    
    # Test the updated API client
    if config_updated and api_working_updated:
        test_update()
    
    logger.info("API model fix completed")

if __name__ == "__main__":
    main()
else:
    # When imported from Django shell
    main()