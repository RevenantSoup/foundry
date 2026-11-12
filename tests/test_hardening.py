import json
from click.testing import CliRunner
from foundry.cli import cli

def test_version_and_structured_errors_hide_secrets(tmp_path,monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY','secret-provider-key')
    result=CliRunner().invoke(cli,['--version'])
    assert result.exit_code==0 and '0.1.0' in result.output
    result=CliRunner().invoke(cli,['--root',str(tmp_path),'filter','--batch','missing'])
    assert result.exit_code==1
    record=next(json.loads(line) for line in result.output.splitlines() if line.startswith('{'))
    assert record['command']=='filter' and record['batch_id']=='missing' and record['timestamp']


def test_log_redacts_provider_admin_and_buyer_secrets(tmp_path,monkeypatch,capsys):
    from foundry.logging import event
    monkeypatch.setenv('OPENAI_API_KEY','private-provider-value')
    monkeypatch.setenv('FOUNDRY_ADMIN_PASSWORD','private-admin-value')
    logfile=tmp_path/'events.jsonl'
    monkeypatch.setenv('FOUNDRY_LOG_FILE',str(logfile))
    event('warning','harvest','batch-123',
          'private-provider-value private-admin-value Bearer bearer-value fdy_buyer-value')
    stderr=capsys.readouterr().err
    assert stderr==logfile.read_text()
    record=json.loads(stderr)
    assert record['batch_id']=='batch-123' and record['timestamp']
    for secret in ('private-provider-value','private-admin-value','bearer-value','fdy_buyer-value'):
        assert secret not in stderr
