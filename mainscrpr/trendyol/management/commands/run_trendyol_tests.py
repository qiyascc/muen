"""
Admin command to run all Trendyol integration tests.
This provides a convenient way to execute all tests from the command line
and see detailed results.
"""
import os
import sys
import unittest
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from loguru import logger
import json

class Command(BaseCommand):
    help = 'Run all Trendyol API integration tests'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Display detailed test output',
        )
        parser.add_argument(
            '--test-module',
            type=str,
            help='Run only a specific test module (e.g., "test_api_connection")',
        )
        parser.add_argument(
            '--test-case',
            type=str,
            help='Run only a specific test case (e.g., "TrendyolAPIConnectionTest")',
        )
        parser.add_argument(
            '--test-method',
            type=str,
            help='Run only a specific test method (e.g., "test_brands_api_connection")',
        )
        parser.add_argument(
            '--include-product-sync',
            action='store_true',
            help='Include product synchronization tests (may create actual products in Trendyol)',
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output results in JSON format',
        )

    def handle(self, *args, **options):
        """Run the tests based on command line arguments"""
        
        start_time = time.time()
        
        # Configure test discovery pattern
        discover_pattern = 'trendyol.tests'
        if options['test_module']:
            discover_pattern += '.' + options['test_module']
        
        # Set up the test loader
        loader = unittest.TestLoader()
        
        # Discover all tests in the trendyol.tests package
        if options['test_method'] and options['test_case']:
            # Run a specific test method in a specific test case
            suite = loader.loadTestsFromName(
                f'trendyol.tests.{options["test_module"]}.{options["test_case"]}.{options["test_method"]}'
            )
        elif options['test_case']:
            # Run all test methods in a specific test case
            suite = loader.loadTestsFromName(
                f'trendyol.tests.{options["test_module"]}.{options["test_case"]}'
            )
        else:
            # Run all discovered tests
            suite = loader.discover('mainscrpr', pattern='test_*.py')
        
        # Filter out product sync tests if not explicitly included
        if not options['include_product_sync']:
            # Create a filtered test suite
            filtered_suite = unittest.TestSuite()
            for test in suite:
                for subtest in test:
                    if hasattr(subtest, '_testMethodName') and 'sync_product' not in subtest._testMethodName:
                        filtered_suite.addTest(subtest)
            suite = filtered_suite
            
        # Configure the test runner
        runner = unittest.TextTestRunner(
            verbosity=2 if options['verbose'] else 1,
            failfast=False
        )
        
        # Run the tests
        self.stdout.write(self.style.SUCCESS(f"Starting Trendyol API tests at {timezone.now()}"))
        self.stdout.write(self.style.SUCCESS('-' * 80))
        
        # Capture the test results
        result = runner.run(suite)
        
        # Calculate test duration
        duration = time.time() - start_time
        
        # Print test summary
        self.stdout.write(self.style.SUCCESS('-' * 80))
        self.stdout.write(self.style.SUCCESS(f"Finished in {duration:.2f} seconds"))
        self.stdout.write(self.style.SUCCESS(f"Ran {result.testsRun} tests"))
        
        if result.wasSuccessful():
            self.stdout.write(self.style.SUCCESS("All tests PASSED!"))
            status = "PASS"
        else:
            self.stdout.write(self.style.ERROR(f"Tests FAILED: {len(result.failures)} failures, {len(result.errors)} errors"))
            status = "FAIL"
            
            # Output failure details
            if result.failures:
                self.stdout.write(self.style.ERROR("\nFailures:"))
                for i, (test, traceback) in enumerate(result.failures, 1):
                    self.stdout.write(self.style.ERROR(f"\n{i}. {test}"))
                    if options['verbose']:
                        self.stdout.write(self.style.ERROR(traceback))
                        
            if result.errors:
                self.stdout.write(self.style.ERROR("\nErrors:"))
                for i, (test, traceback) in enumerate(result.errors, 1):
                    self.stdout.write(self.style.ERROR(f"\n{i}. {test}"))
                    if options['verbose']:
                        self.stdout.write(self.style.ERROR(traceback))
        
        # Output in JSON format if requested
        if options['json']:
            json_result = {
                'timestamp': timezone.now().isoformat(),
                'duration': duration,
                'tests_run': result.testsRun,
                'status': status,
                'failures': len(result.failures),
                'errors': len(result.errors),
                'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
                'details': {
                    'failures': [{'test': str(test), 'traceback': traceback} for test, traceback in result.failures],
                    'errors': [{'test': str(test), 'traceback': traceback} for test, traceback in result.errors],
                    'skipped': [{'test': str(test), 'reason': reason} for test, reason in 
                               (result.skipped if hasattr(result, 'skipped') else [])]
                }
            }
            self.stdout.write(json.dumps(json_result, indent=2))
        
        # Return appropriate exit code
        if not result.wasSuccessful():
            sys.exit(1)