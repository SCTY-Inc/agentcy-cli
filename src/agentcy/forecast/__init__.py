"""
MiroFish Backend
"""

import warnings

# Suppress multiprocessing resource_tracker warnings (from third-party libs like transformers)
warnings.filterwarnings("ignore", message=".*resource_tracker.*")
