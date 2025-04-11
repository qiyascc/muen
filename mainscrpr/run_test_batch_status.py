#!/usr/bin/env python3
"""
Run the test_batch_status.py script directly.
"""

import os
import sys
import django
import logging
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stdout, level="INFO")

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mainscrpr.settings")
django.setup()

# Import the test function
from test_batch_status import main

# Run the test
if __name__ == "__main__":
    print("Running batch status test...")
    main()