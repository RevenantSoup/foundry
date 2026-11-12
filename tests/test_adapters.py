import io
import imagehash
from PIL import Image
import pytest
from foundry.db import Database
from foundry.adapters.openverse import OpenverseAdapter
from foundry.adapters.youtube import YouTubeAdapter, extract_frames
from foundry.quota import QuotaExceeded

def test_offline_sources_and_reencode(tmp_path):
    db = Database(tmp_path/'db')
    for adapter in (OpenverseAdapter(), YouTubeAdapter(db)):
        rows = adapter.search('glasses',2)
        assert len(rows) == 2
        row = rows[0]
        payload = adapter.fetch(row)
        image = Image.open(io.BytesIO(payload))
        image.save(tmp_path/'copy.jpg',quality=85)
        row.phash = str(imagehash.phash(image))
        row.batch_id = 'b'
        assert db.insert(row)
        row.id += '-copy'; row.source_url += '/copy'
        row.phash = str(imagehash.phash(Image.open(tmp_path/'copy.jpg')))
        assert not db.insert(row)
        assert adapter.licence(row) == row.licence

def test_youtube_quota_before_network(tmp_path):
    db = Database(tmp_path/'db')
    from foundry.quota import consume
    consume(db,'youtube',10000)
    with pytest.raises(QuotaExceeded):
        YouTubeAdapter(db,offline=False,api_key='fake').search('x',1)

def test_short_video_has_no_untrimmed_frames(tmp_path):
    import subprocess
    subprocess.run(['ffmpeg','-loglevel','error','-f','lavfi','-i',
                    'color=red:s=64x64:d=3','-y',str(tmp_path/'v.mp4')],check=True)
    assert extract_frames(tmp_path/'v.mp4',tmp_path/'frames') == []
