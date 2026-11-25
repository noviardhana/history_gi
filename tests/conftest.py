import sys
from pathlib import Path

# make `import pipeline` work when pytest is started from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
