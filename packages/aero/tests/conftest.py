import sys
import os

# Appends src/ to sys.path so tests can import amx modules natively
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
