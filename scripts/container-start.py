#!/usr/local/bin/python
"""Expand the trusted image SDK once per archive version, then exec the service."""
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

archive=Path('/opt/foundry-python.tar.xz')
root=Path(os.environ.get('FOUNDRY_ROOT','/data'))
cache=root/'.runtime';cache.mkdir(parents=True,exist_ok=True)
digest=hashlib.sha256()
with archive.open('rb') as stream:
    for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
destination=cache/digest.hexdigest()
with (cache/'extract.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    if not (destination/'ready').exists():
        staging=Path(tempfile.mkdtemp(prefix='sdk-',dir=cache))
        try:
            with tarfile.open(archive,'r:*') as packed:
                packed.extractall(staging,filter='data')
            (staging/'ready').write_text(digest.hexdigest())
            staging.rename(destination)
        finally:
            if staging.exists():shutil.rmtree(staging)
env=dict(os.environ)
env['PATH']=str(destination/'foundry-bin')+os.pathsep+env.get('PATH','')
env['PYTHONPATH']='/app'+os.pathsep+str(destination)+os.pathsep+env.get('PYTHONPATH','')
arguments=sys.argv[1:] or ['foundry','--help']
commands={'plan','harvest','filter','qa','package','price','api-key','schedule','run-scheduled'}
if arguments[0].startswith('-') or arguments[0] in commands:
    arguments=['foundry',*arguments]
os.execvpe(arguments[0],arguments,env)
