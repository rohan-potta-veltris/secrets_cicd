import os
import sys

# Ensure `app/` is importable as a top-level module regardless of the
# directory pytest is invoked from.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
