"""Verification interfaces. Stub verdicts are fixtures, never human QA."""
from abc import ABC, abstractmethod
import base64
import requests
from ..http import request_with_retry
from ..usage import log_usage

class Verifier(ABC):
    @abstractmethod
    def verify(self,path,prompt,checklist): ...

class StubVerifier(Verifier):
    def verify(self,path,prompt,checklist):
        return 'accept'

class OpenAIVerifier(Verifier):
    def __init__(self,api_key,model='gpt-4o-mini',session=None,db=None,batch_id=''):
        self.api_key,self.model=api_key,model
        self.session=session or requests.Session()
        self.db,self.batch_id=db,batch_id
    def verify(self,path,prompt,checklist):
        from PIL import Image
        import io
        with Image.open(path) as image:
            output=io.BytesIO()
            image.convert('RGB').save(output,format='JPEG')
        encoded=base64.b64encode(output.getvalue()).decode()
        response=request_with_retry(self.session,'post','https://api.openai.com/v1/chat/completions',
            db=self.db,source='openai',batch_id=self.batch_id,
            headers={'Authorization':f'Bearer {self.api_key}'},
            json={'model':self.model,'temperature':0,'messages':[
                {'role':'system','content':'Return exactly accept or reject. Accept only if the image satisfies the prompt and every checklist item.'},
                {'role':'user','content':[
                    {'type':'text','text':prompt+'\n'+'\n'.join(checklist)},
                    {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+encoded,'detail':'low'}}]}]},
            timeout=60)
        response.raise_for_status()
        data=response.json()
        if data.get('usage'):
            log_usage(self.db,'openai',self.batch_id,event='tokens',token_count=data['usage'].get('total_tokens'))
        verdict=data['choices'][0]['message']['content'].strip().lower()
        if verdict not in ('accept','reject'):
            log_usage(self.db,'openai',self.batch_id,event='validation',is_error=1,detail='invalid_verdict')
            raise ValueError('Invalid model verdict')
        return verdict
