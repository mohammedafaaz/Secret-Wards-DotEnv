import io,time,zipfile
import pytest
from fastapi.testclient import TestClient
from backend.app import app,MAX_BYTES,MAX_FILES
import backend.app as bridge

@pytest.fixture
def client():
 bridge.session_store.clear()
 with TestClient(app) as test_client:yield test_client
 bridge.session_store.clear()

def wait(client):
 for _ in range(400):
  s=client.get('/api/run').json()
  if s['status'] in ('completed','failed'):return s
  time.sleep(.05)
 raise AssertionError('run timed out')
def test_upload_diagnostic_locked(client,monkeypatch):
 monkeypatch.setenv('SHEILD_RULES_DIAGNOSTIC','1');assert client.post('/api/run/upload',files=[('files',('note.txt',b'Patient: Fictional Example\nMetformin 500 mg','text/plain'))]).status_code==200;s=wait(client);assert s['status']=='completed' and s['counts']['files_total']==1
 if not s['modelActive']:assert not s['releaseApproved'] and client.get('/api/release/files').status_code==409
 assert client.post('/api/run/upload',files=[('files',('../escape.txt',b'no','text/plain'))]).status_code==400
 assert client.post('/api/run/practice',headers={'Origin':'https://external.invalid'}).status_code==403
def test_upload_oversized_request_rejected(client,monkeypatch):
 monkeypatch.delenv('SHEILD_RULES_DIAGNOSTIC',raising=False)
 oversized=b'x'*(MAX_BYTES+1)
 r=client.post('/api/run/upload',files=[('files',('big.txt',oversized,'text/plain'))])
 # Middleware rejects oversized requests before reaching the handler
 assert r.status_code==413
def test_upload_many_files_exceeds_limit(client,monkeypatch):
 monkeypatch.delenv('SHEILD_RULES_DIAGNOSTIC',raising=False)
 files=[('files',(f'file_{i}.txt',b'clinical note','text/plain')) for i in range(MAX_FILES+1)]
 r=client.post('/api/run/upload',files=files)
 assert r.status_code==400
def test_upload_malformed_multipart_rejected(client,monkeypatch):
 monkeypatch.delenv('SHEILD_RULES_DIAGNOSTIC',raising=False)
 r=client.post('/api/run/upload',content=b'not multipart at all',headers={'content-type':'multipart/form-data; boundary=xyz'})
 assert r.status_code==400
def test_upload_zip_bomb_rejected(client,monkeypatch):
 monkeypatch.delenv('SHEILD_RULES_DIAGNOSTIC',raising=False)
 # Create content that exceeds MAX_BYTES (64 MB) when uncompressed
 # but compresses well below that due to repetition
 chunk=b'clinical patient note ' * 100000  # ~2.1 MB each
 needed=(MAX_BYTES // len(chunk)) + 2  # enough to exceed 64 MB uncompressed
 buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
  for i in range(needed):
   z.writestr(f'file_{i}.txt',chunk)
 bomb=buf.getvalue()
 r=client.post('/api/run/upload',files=[('files',('bomb.zip',bomb,'application/zip'))])
 assert r.status_code==400
def test_failed_upload_clears_stale_release(client,monkeypatch):
 monkeypatch.setenv('SHEILD_RULES_DIAGNOSTIC','1')
 client.get('/api/run')
 session=bridge.session_store.peek(client.cookies.get(bridge.SESSION_COOKIE))
 with session.lock:
  session.release['archive.zip']=b'stale'
  session.state['releaseApproved']=True
 # Submit an oversized request that must fail and clear stale release
 oversized=b'y'*(MAX_BYTES+1)
 r=client.post('/api/run/upload',files=[('files',('big.txt',oversized,'text/plain'))])
 assert r.status_code==413
 # Stale release must be cleared
 assert client.get('/api/release/files').status_code==409
