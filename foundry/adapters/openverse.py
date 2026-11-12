"""Openverse image search. Only the requested CC licence families are admitted."""
import hashlib
import os
import requests
from .base import Adapter, fixture_rows, fixture_bytes
from ..models import Row
from ..http import request_with_retry

class OpenverseAdapter(Adapter):
    def __init__(self, offline=True, session=None, db=None, batch_id=""):
        self.offline = offline
        self.db,self.batch_id=db,batch_id
        self.session = session or requests.Session()
        self.downloads = {}
        self.headers={'User-Agent':'Foundry/0.3 (+https://github.com/RevenantSoup/foundry)'}
        token=os.environ.get('OPENVERSE_API_KEY')
        if token:self.headers['Authorization']='Bearer '+token
    def search(self, q, limit):
        if self.offline:
            return fixture_rows('openverse',q,limit,'CC0')
        rows = []
        page = 1
        while len(rows) < limit:
            response = request_with_retry(self.session,'get','https://api.openverse.org/v1/images/',db=self.db,source='openverse',batch_id=self.batch_id,headers=self.headers,
                params={'q':q,'license':'cc0,by,by-sa','page_size':min(200,limit-len(rows)),
                        'page':page}, timeout=30)
            response.raise_for_status()
            result = response.json()
            for item in result.get('results',[]):
                licence = {'cc0':'CC0','by':'CC-BY','by-sa':'CC-BY-SA'}.get(item.get('license'))
                author = item.get('creator')
                if not licence or not isinstance(author,str) or not author.strip():
                    if self.db:
                        with self.db.conn:
                            self.db.drop(Row(id=str(item.get('id','unknown')),source='openverse',
                                source_url=item.get('url',''),licence='',attribution='',
                                batch_id=self.batch_id),'missing_licence_or_attribution')
                    continue
                id = hashlib.sha256(('openverse:'+item['id']).encode()).hexdigest()[:24]
                row = Row(id=id,source='openverse',source_url=item['url'],
                          licence=licence,attribution=author)
                row.metadata={'licence_url':item.get('license_url') or {
                    'CC0':'https://creativecommons.org/publicdomain/zero/1.0/',
                    'CC-BY':'https://creativecommons.org/licenses/by/'+str(item.get('license_version') or '')+'/',
                    'CC-BY-SA':'https://creativecommons.org/licenses/by-sa/'+str(item.get('license_version') or '')+'/'}[licence],
                    'creator':author,'title':item.get('title') or '',
                    'source_page_url':item.get('foreign_landing_url') or item['url']}
                row.metadata['licence_url']=row.metadata['licence_url'].replace('by//','by/').replace('by-sa//','by-sa/')
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
        response = request_with_retry(self.session,'get',self.downloads[row.id],db=self.db,source='openverse',batch_id=self.batch_id,headers={'User-Agent':self.headers['User-Agent']},timeout=60)
        response.raise_for_status()
        return response.content
    def licence(self, row):
        return row.licence
