"""TEST ONLY real worker with fake Stripe SDK and controlled transport faults."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from mock_stripe import install
install()
from foundry.worker import WorkerServer,Handler

class TestHandler(Handler):
    fault='normal'
    def do_POST(self):
        if self.path=='/__test__/transport':
            if not self.authorized():return
            type(self).fault=self.read_payload()['mode']
            self.send_json(200,{'ok':True})
            return
        if type(self).fault=='unauthorized':
            self.error(401,'unauthorized','Invalid worker credentials')
            return
        if type(self).fault=='empty':
            self.send_response(204)
            self.end_headers()
            return
        if type(self).fault=='encoded':
            self.send_response(200)
            self.send_header('Content-Encoding','gzip')
            self.send_header('Content-Length','2')
            self.end_headers()
            self.wfile.write(b'{}')
            return
        if type(self).fault=='drop':
            self.close_connection=True
            self.connection.close()
            return
        super().do_POST()

WorkerServer(('127.0.0.1',8100),TestHandler).serve_forever()
