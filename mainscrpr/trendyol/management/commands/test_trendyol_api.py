"""
Command to test Trendyol API connectivity and functionality.
This is a simple wrapper around the run_trendyol_verification.py script
for convenient access from the command line.
"""
import os
import sys
import subprocess
from django.core.management.base import BaseCommand
from django.utils import timezone
from loguru import logger

class Command(BaseCommand):
    help = 'Test Trendyol API connectivity and functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Display detailed test output'
        )
        parser.add_argument(
            '--include-product-ops',
            action='store_true',
            help='Include product operations tests'
        )

    def handle(self, *args, **options):
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 
                                 'run_trendyol_verification.py')
        
        if not os.path.exists(script_path):
            self.stderr.write(self.style.ERROR(f"Verification script not found at {script_path}"))
            return
            
        cmd = [sys.executable, script_path]
        
        if options['verbose']:
            cmd.append('--verbose')
            
        if options['include_product_ops']:
            cmd.append('--include-product-ops')
            
        self.stdout.write(self.style.SUCCESS(f"Running Trendyol API tests at {timezone.now()}"))
        self.stdout.write(self.style.SUCCESS(f"Command: {' '.join(cmd)}"))
        self.stdout.write(self.style.SUCCESS('-' * 80))
        
        try:
            # Run the command and stream output to console
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Stream output
            for line in process.stdout:
                self.stdout.write(line.rstrip())
                
            # Wait for process to complete
            exit_code = process.wait()
            
            if exit_code == 0:
                self.stdout.write(self.style.SUCCESS("\nAll tests passed successfully!"))
            else:
                self.stdout.write(self.style.ERROR(f"\nTests failed with exit code {exit_code}"))
                
            return exit_code
                
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error running tests: {str(e)}"))
            return 1