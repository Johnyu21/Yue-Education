"""Compatibility entry point for the unified Dify 1.12.1 builder."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from build_dify_workflows import build, write

def main():
    write("enterprise")
    print("Built enterprise workflow using shared contracts.")

if __name__ == "__main__":
    main()
