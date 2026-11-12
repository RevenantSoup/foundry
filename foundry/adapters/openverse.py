"""Openverse image search. Only the requested CC licence families are admitted."""
import hashlib
import requests
from .base import Adapter, fixture_rows, fixture_bytes
from ..models import Row

class OpenverseAdapter(Adapter):
    def __init__(self, offline=True, session=None):
        self.offline = offline
        self.session = session or requests.Session()
        self.downloads = {}
    def search(self, q, limit):
        if self.offline:
            return fixture_rows('openverse',q,limit,'CC0')
        rows = []
        page = 1
        while len(rows) < limit:
            response = self.session.get('https://api.openverse.org/v1/images/',
                params={'q':q,'license':'cc0,by,by-sa','page_size':min(200,limit-len(rows)),
                        'page':page}, timeout=30)
            response.raise_for_status()
            result = response.json()
            for item in result.get('results',[]):
                licence = {'cc0':'CC0','by':'CC-BY','by-sa':'CC-BY-SA'}.get(item.get('license'))
                author = item.get('creator')
                if not licence or not author:
                    continue
                id = hashlib.sha256(('openverse:'+item['id']).encode()).hexdigest()[:24]
                row = Row(id=id,source='openverse',source_url=item.get('foreign_landing_url') or item['url'],
                          licence=licence,attribution=author)
                self.downloads[id] = item['url']
                rows.append(row)
                if len(rows) == limit:
                    break
            if not result.get('next') or not result.get('results'):
                break
            page += 1
        return rows
    def fetch(self, row):
        if self.offline:
            return fixture_bytes(row)
        response = self.session.get(self.downloads[row.id],timeout=60)
        response.raise_for_status()
        return response.content
    def licence(self, row):
        return row.licence
