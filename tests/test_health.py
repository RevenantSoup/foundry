from web.bridge import health_payload

def test_health_initializes_and_checks_database(tmp_path,monkeypatch):
    monkeypatch.setenv('FOUNDRY_ROOT',str(tmp_path))
    assert health_payload()=={'db':'ok'}
    assert (tmp_path/'foundry.sqlite3').exists()

def test_redaction_covers_credentials(monkeypatch):
    from foundry.logging import redact
    monkeypatch.setenv('FOUNDRY_ADMIN_PASSWORD','private-admin-password')
    value=redact('private-admin-password Bearer unknown-secret fdy_private-buyer-key')
    assert 'private-admin-password' not in value and 'unknown-secret' not in value and 'fdy_private' not in value
