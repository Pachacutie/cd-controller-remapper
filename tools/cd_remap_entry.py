"""PyInstaller entry point — avoids relative import issues."""
import sys
from pathlib import Path

# Ensure tools/ is on the path for the cd_remap package
sys.path.insert(0, str(Path(__file__).parent))

from cd_remap.__main__ import main

if __name__ == "__main__":
    main()
