"""Read-only mTLS source for locally approved NDJSON parts; no dynamic paths or code."""
import argparse
import hashlib
import ssl
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from level1_core.contracts import check,loads
from level1_core.bindings import identifier
from level1_core.transport import pins

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path not in self.server.files:self.send_error(404);return
        with self.server.files[self.path].open('rb') as file:raw=file.read(65537)
        if len(raw)>65536:self.send_error(413);return
        self.send_response(200);self.send_header('Content-Type','application/x-ndjson')
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)

class PartServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,tls_context,client_pins,files):
        self.context,self.allowed=tls_context,pins(list(client_pins))
        self.files=dict(files)
        self.slots=threading.BoundedSemaphore(8)
        super().__init__(address,Handler)
    def get_request(self):
        raw,address=super().get_request();raw.settimeout(3)
        try:
            conn=self.context.wrap_socket(raw,server_side=True)
            pin=hashlib.sha256(conn.getpeercert(binary_form=True)).hexdigest()
            if pin not in self.allowed:conn.close();raise OSError('Data client not allowed')
            return conn,address
        except Exception:raw.close();raise
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):self.shutdown_request(request);return
        try:super().process_request(request,address)
        except Exception:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()
    def handle_error(self,*args):pass

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--source-id',required=True)
    parser.add_argument('--parts-dir',required=True)
    parser.add_argument('--tls-config',required=True)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=9443)
    args=parser.parse_args()
    manifest=check('data_manifest',loads(Path(args.manifest).read_bytes()))
    config=loads(Path(args.tls_config).read_bytes());tls=config['tls']
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(tls['cert'],tls['key']);context.load_verify_locations(cafile=tls['ca']);context.verify_mode=ssl.CERT_REQUIRED
    root=Path(args.parts_dir).resolve();files={}
    for part in manifest['parts']:
        if part['source_id']!=args.source_id:continue
        identifier(part['part_id']);identifier(part['source_id'])
        target=(root/(part['part_id']+'.ndjson')).resolve()
        if not target.is_relative_to(root) or not target.is_file():raise ValueError('Invalid part file')
        files['/v1/data/parts/'+part['part_id']]=target
    if not files:raise ValueError('No approved parts for source')
    server=PartServer((args.host,args.port),context,config['client_pins'],files)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
