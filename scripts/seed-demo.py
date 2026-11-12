#!/usr/bin/env python3
"""Create two labeled synthetic fixtures. Never calls live source APIs."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from foundry.seed import seed_demo
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=Path(os.environ.get('FOUNDRY_ROOT',Path(__file__).resolve().parents[1]/'data')))
args=parser.parse_args()
print(json.dumps(seed_demo(args.root),indent=2))
