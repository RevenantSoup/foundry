"""Verification interfaces. Stub verdicts are fixtures, never human QA."""
from abc import ABC, abstractmethod
import base64
import requests

class Verifier(ABC):
    @abstractmethod
    def verify(self,path,prompt,checklist): ...

class StubVerifier(Verifier):
    def verify(self,path,prompt,checklist):
        return 'accept'

class OpenAIVerifier(Verifier):
    def __init__(self,api_key,model='gpt-4o-mini',session=None):
        self.api_key,self.model=api_key,model
        self.session=session or requests.Session()
    def verify(self,path,prompt,checklist):
        from PIL import Image
        import io
        with Image.open(path) as image:
            output=io.BytesIO()
            image.convert('RGB').save(output,format='JPEG')
        encoded=base64.b64encode(output.getvalue()).decode()
        response=self.session.post('https://api.openai.com/v1/chat/completions',
            headers={'Authorization':f'Bearer {self.api_key}'},
            json={'model':self.model,'temperature':0,'messages':[
                {'role':'system','content':'Return exactly accept or reject. Accept only if the image satisfies the prompt and every checklist item.'},
                {'role':'user','content':[
                    {'type':'text','text':prompt+'\n'+'\n'.join(checklist)},
                    {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+encoded,'detail':'low'}}]}]},
            timeout=60)
        response.raise_for_status()
        verdict=response.json()['choices'][0]['message']['content'].strip().lower()
        if verdict not in ('accept','reject'):
            raise ValueError('Invalid model verdict')
        return verdict
