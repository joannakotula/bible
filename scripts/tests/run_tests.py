import unittest
import os

TESTS_DIR=os.path.dirname(os.path.realpath(__file__))

loader = unittest.TestLoader()
suite = loader.discover(start_dir=TESTS_DIR, pattern="*_test.py")

runner = unittest.TextTestRunner()
runner.run(suite)