import importlib.util
from pathlib import Path
import pytest

SPEC=importlib.util.spec_from_file_location('bridge',Path(__file__).parents[1]/'bridge.py')
bridge=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)

def test_empty_snapshot(tmp_path,monkeypatch):
    monkeypatch.setenv('FOUNDRY_ROOT',str(tmp_path))
    state=bridge.snapshot()
    assert state['batches']==[] and state['totals']['harvested']==0

def test_path_validation():
    with pytest.raises(ValueError): bridge.identifier('../escape')
    with pytest.raises(ValueError): bridge.identifier('bad/name')

def test_unknown_action_rejected(tmp_path,monkeypatch):
    monkeypatch.setenv('FOUNDRY_ROOT',str(tmp_path))
    with pytest.raises(ValueError): bridge.command_for('delete','a'*32,{})

def test_platform_rights_not_for_sale():
    assert bridge.sale_clearance(['CC0','CC-BY'])
    assert not bridge.sale_clearance(['CC0','platform_public_as_is'])
    assert not bridge.sale_clearance(['unknown'])
