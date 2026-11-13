"""TEST ONLY subprocess wrapper to install the SDK fake in local bridge processes."""
import runpy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mock_stripe import install
install()
sys.argv=sys.argv[1:]
runpy.run_path(sys.argv[0],run_name='__main__')
