"""
Pytest configuration for TaxGuideAI tests.
Adds the src directory to the Python path for importing taxguideai modules.
"""
import sys
from pathlib import Path

# Add src directory to path so tests can import taxguideai
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))
