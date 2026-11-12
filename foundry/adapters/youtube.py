"""YouTube metadata with explicit, user-supplied licensed local media.

The Data API does not provide a media download endpoint. Live harvesting uses
files named <video-id>.mp4 in --video-dir; it never scrapes streaming URLs.
"""
import hashlib
import re
from pathlib import Path
import ffmpeg
import requests
from .base import Adapter, fixture_rows, fixture_bytes
from ..models import Row
from ..quota import consume

def extract_frames(path, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    duration = float(ffmpeg.probe(str(path))['format']['duration'])
    if duration <= 4:
        return []
    # showinfo emits actual timestamps after select; offset is restored below.
    stream = ffmpeg.input(str(path),ss=2,t=duration-4).video
    stream = stream.filter('select','gt(scene,0.3)').filter('showinfo')
    _, stderr = (ffmpeg.output(stream,str(destination/'%03d.png'),vsync='vfr',vframes=40)
                 .overwrite_output().run(capture_stdout=True,capture_stderr=True))
    timestamps = [float(x) for x in re.findall(rb'pts_time:([0-9.]+)',stderr)]
    files = sorted(destination.glob('[0-9][0-9][0-9].png'))[:40]
    return [(file,round((ts+2)*1000)) for file,ts in zip(files,timestamps)
            if 2 <= ts+2 < duration-2]

class YouTubeAdapter(Adapter):
    def __init__(self, db, offline=True, api_key=None, video_dir=None, session=None):
        self.db, self.offline, self.api_key = db, offline, api_key
        self.video_dir = Path(video_dir) if video_dir else None
        self.session = session or requests.Session()
        self.files = {}
    def search(self,q,limit):
        if self.offline:
            return fixture_rows('youtube',q,limit,'platform_public_as_is')
        if not self.api_key:
            raise ValueError('YOUTUBE_API_KEY is required')
        rows, token = [], None
        while len(rows) < limit:
            consume(self.db,'youtube',100)
            response = self.session.get('https://www.googleapis.com/youtube/v3/search',
                params={'key':self.api_key,'part':'snippet','q':q,'type':'video',
                        'maxResults':min(50,limit-len(rows)),'pageToken':token},timeout=30)
            response.raise_for_status()
            data = response.json()
            for item in data.get('items',[]):
                video = item['id']['videoId']
                path = self.video_dir / (video+'.mp4') if self.video_dir else None
                if not path or not path.is_file():
                    continue
                for file,ts in extract_frames(path,self.video_dir/'.foundry-frames'/video):
                    id = hashlib.sha256(f'youtube:{video}:{ts}'.encode()).hexdigest()[:24]
                    row = Row(id=id,source='youtube',source_url=f'https://www.youtube.com/watch?v={video}&t={ts/1000}',
                              licence='platform_public_as_is',
                              attribution=item['snippet']['channelTitle'],frame_ts_ms=ts)
                    rows.append(row); self.files[id]=file
                    if len(rows)==limit:
                        break
                if len(rows)==limit:
                    break
            token = data.get('nextPageToken')
            if not token:
                break
        return rows
    def fetch(self,row):
        return fixture_bytes(row) if self.offline else self.files[row.id].read_bytes()
    def licence(self,row):
        return row.licence
