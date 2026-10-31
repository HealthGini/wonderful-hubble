import unittest
import os
import sys

# Ensure automated test runs never load live `.env` credentials or send real external emails
os.environ["GOODDEEDS_SKIP_DOTENV"] = "1"
os.environ.setdefault("EMAIL_PROVIDER", "simulated")

# Add workspace root to sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(TESTS_DIR)
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

def suite():
    loader = unittest.TestLoader()
    suite = loader.discover(TESTS_DIR, pattern="test_*.py")
    return suite

if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite())
    sys.exit(not result.wasSuccessful())
