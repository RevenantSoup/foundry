import pytest
from foundry.db import Database
from foundry.quota import consume, QuotaExceeded

def test_quota_hard_gate(tmp_path):
    db = Database(tmp_path/'db')
    consume(db, 'youtube', 10000)
    with pytest.raises(QuotaExceeded) as error: consume(db, 'youtube', 100)
    assert error.value.exit_code == 2
    assert db.conn.execute('select units from quota').fetchone()[0] == 10000
