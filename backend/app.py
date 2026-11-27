"""Local synthetic-data web bridge. Raw input and candidate output remain in process memory."""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import threading
import time
import zipfile
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
import dataclasses
from email.parser import BytesParser
from email import policy
from functools import lru_cache
from pathlib import Path,PurePosixPath
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import JSONResponse,Response,FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sheild.engine import run_pipeline,directory_entries,load_model,_safe_input_path
from models.v2.model_features import VERSION as MODEL_FEATURE_VERSION
from sheild.verify import verify

ROOT=Path(__file__).resolve().parents[1]
KIT=ROOT/'Secret-Wards-ToolKit-main'
MAX_BYTES=64*1024*1024
MAX_FILES=5000
MAX_ZIP_COMPRESSED=64*1024*1024
SESSION_TTL_SECONDS=30*60
MAX_SESSIONS=4
MAX_SESSION_OUTPUT_BYTES=128*1024*1024
SESSION_COOKIE='shield_session'
SECRET=os.environ.get('RAKSHA_SECRET') or secrets.token_hex(32)


def initial_state():
  return {'status':'idle','releaseApproved':False,'stages':{},'counts':{},'contractValid':None,'verification':None,'detailedFindings':[]}


@dataclass
class Session:
 identifier: str
 secret: str
 state: dict=field(default_factory=initial_state)
 release: dict=field(default_factory=dict)
 last_activity: float=field(default_factory=time.monotonic)
 in_flight: int=0
 lock: threading.RLock=field(default_factory=threading.RLock,repr=False)


class SessionStore:
 def __init__(self):
  self._sessions=OrderedDict()
  self._lock=threading.RLock()

 def _retire(self,identifier,session):
  self._sessions.pop(identifier,None)
  with session.lock:
   session.release.clear()
   session.state.clear()

 def _expire(self,now):
  for identifier,session in list(self._sessions.items()):
   if session.in_flight==0 and session.state.get('status') not in ('queued','running') and now-session.last_activity>=SESSION_TTL_SECONDS:
    self._retire(identifier,session)

 def _new(self):
  identifier=secrets.token_urlsafe(32)
  derived=hmac.new(SECRET.encode('utf-8'),identifier.encode('ascii'),hashlib.sha256).hexdigest()
  return Session(identifier,derived)

 def acquire(self,identifier):
  now=time.monotonic()
  with self._lock:
   self._expire(now)
   if identifier:
    session=self._sessions.get(identifier)
    if session is None:return None
    self._sessions.move_to_end(identifier)
   else:
    if len(self._sessions)>=MAX_SESSIONS:
     evictable=next(((key,value) for key,value in self._sessions.items()
                     if value.in_flight==0 and value.state.get('status') not in ('queued','running')),None)
     if evictable is None:return None
     self._retire(*evictable)
    session=self._new()
    self._sessions[session.identifier]=session
   session.in_flight+=1
   session.last_activity=now
   return session

 def release_request(self,session):
  with self._lock:
   if session.identifier in self._sessions:
    session.in_flight=max(0,session.in_flight-1)
    session.last_activity=time.monotonic()

 def touch(self,session):
  with self._lock:
   if self._sessions.get(session.identifier) is session:
    session.last_activity=time.monotonic()
    self._sessions.move_to_end(session.identifier)

 def peek(self,identifier):
  with self._lock:return self._sessions.get(identifier)

 def clear(self):
  with self._lock:
   for identifier,session in list(self._sessions.items()):self._retire(identifier,session)


app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver'])
session_store=SessionStore()


@app.middleware('http')
async def boundary(request:Request,call_next):
 origin=request.headers.get('origin')
 allowed_origins={'http://localhost:3000','http://127.0.0.1:3000','http://localhost:8000','http://127.0.0.1:8000',
                  'http://127.0.0.1:'+os.environ.get('SHIELD_WEB_PORT','8000'),'http://localhost:'+os.environ.get('SHIELD_WEB_PORT','8000')}
 if origin and origin not in allowed_origins:return JSONResponse({'detail':'Origin not allowed'},403)
 try:length=int(request.headers.get('content-length','0'))
 except ValueError:return JSONResponse({'detail':'Invalid request'},400)
 if length<0:return JSONResponse({'detail':'Invalid request'},400)
 session=None
 is_health=request.url.path=='/api/health'
 if request.url.path.startswith('/api/') and not is_health:
  supplied=request.cookies.get(SESSION_COOKIE)
  session=session_store.acquire(supplied)
  if session is None and request.url.path=='/api/session':
   session=session_store.acquire(None)
   supplied=None
  if session is None:
   status=503 if not supplied else 401
   message='Session capacity reached' if status==503 else 'Session expired or invalid'
   return JSONResponse({'detail':message},status_code=status,headers={'Cache-Control':'no-store'})
  request.state.shield_session=session
  if supplied and supplied!=session.identifier:
   session_store.release_request(session)
   return JSONResponse({'detail':'Session expired or invalid'},401,headers={'Cache-Control':'no-store'})
 if length>MAX_BYTES:
  if session and request.method=='POST' and request.url.path=='/api/run/upload':
   with session.lock:
    if session.state.get('status') not in ('queued','running'):
     session.release.clear()
     session.state.clear()
     session.state.update(status='failed',releaseApproved=False,stages={},counts={},contractValid=None,safeSummary='Import rejected: size limit.')
  response=JSONResponse({'detail':'Import limit'},413)
  if session:session_store.release_request(session)
 else:
  try:
   response=await call_next(request)
  finally:
   if session:session_store.release_request(session)
 if session:
  response.set_cookie(SESSION_COOKIE,session.identifier,max_age=SESSION_TTL_SECONDS,httponly=True,
                      secure=request.url.scheme=='https',samesite='strict',path='/api')
 response.headers['Cache-Control']='no-store'
 response.headers['X-Content-Type-Options']='nosniff'
 return response


@lru_cache(maxsize=1)
def model_available():return load_model(required=False) is not None
@app.get('/api/health')
def health():return {'status':'ready','team':'DOTENV','product':'shield','mode':'local-synthetic','releaseGate':'independent-conservative','modelAvailable':model_available(),'modelFeatureVersion':MODEL_FEATURE_VERSION}
@app.post('/api/session')
def initialize_session():return {'status':'ready'}
@app.get('/api/run')
def current(request:Request):
 session=request.state.shield_session
 with session.lock:return json.loads(json.dumps(session.state))
def update(session,**kw):
 with session.lock:session.state.update(kw)
 session_store.touch(session)
def stage(session,name,status):
 with session.lock:session.state['stages'][name]=status
 session_store.touch(session)
def begin(session):
 with session.lock:
  if session.state['status'] in ('queued','running'):raise HTTPException(409,'Run already active')
  session.release.clear()
  session.state.clear()
  session.state.update(runId=secrets.token_hex(12),status='queued',releaseApproved=False,stages={},counts={},contractValid=None,startedAt=time.time())
 session_store.touch(session)
def safe_path(name):
 name=name.replace('\\','/');_safe_input_path(name);return name
def unzip(data):
 with zipfile.ZipFile(io.BytesIO(data)) as z:
  all_infos=z.infolist()
  if len(all_infos)>MAX_FILES:raise ValueError('archive_limit')
  infos=[i for i in all_infos if not i.is_dir()]
  compressed=sum(i.compress_size for i in infos)
  if len(infos)>MAX_FILES or compressed>MAX_ZIP_COMPRESSED or sum(i.file_size for i in infos)>MAX_BYTES:raise ValueError('archive_limit')
  out=[];seen=set();total=0
  for i in infos:
   if (i.external_attr>>16)&0o170000==0o120000:raise ValueError('symlink')
   name=safe_path(i.filename);key=_safe_input_path(name)
   if key in seen:raise ValueError('duplicate_path')
   seen.add(key)
   with z.open(i) as f:
    data=bytearray()
    while True:
     chunk=f.read(min(65536,MAX_BYTES-total+1))
     if not chunk:break
     total+=len(chunk)
     if total>MAX_BYTES or len(data)+len(chunk)>i.file_size:raise ValueError('archive_limit')
     data.extend(chunk)
   if len(data)!=i.file_size:raise ValueError('archive_size')
   out.append((name,bytes(data)))
  return out
def run(entries,session):
 with session.lock:
  session.release.clear()
  session.state['status']='running'
  session.state['releaseApproved']=False
 session_store.touch(session)
 phase='model_initialization'
 try:
  diagnostic=os.environ.get('SHEILD_RULES_DIAGNOSTIC')=='1'
  model=None if diagnostic else load_model(required=True);artifacts={}
  phase='processing'
  session_stage=lambda name,status:stage(session,name,status)
  report,docs=run_pipeline(entries,artifacts,session.secret,model,session_stage)
  phase='verification';stage(session,'verification','running');v=verify(entries,artifacts,docs)
  approved=not diagnostic and model is not None and v.get('approved') is True and v.get('contractValid') is True and v.get('findings') == {}
  detailed_findings = v.get('detailed_findings',[])
  detailed_findings_serializable = [dataclasses.asdict(f) for f in detailed_findings] if detailed_findings else []
  update(session,counts=report['counts'],contractValid=v['contractValid'],verification=v,detailedFindings=detailed_findings_serializable,resources=report['resources'],riskProxy=report['risk_proxy'],modelActive=model is not None)
  stage(session,'verification','completed' if approved else 'failed')
  if approved:
   phase='release_generation'
   buf=io.BytesIO()
   with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
    for k,b in sorted(artifacts.items()):
     if k.startswith('sanitized/'):z.writestr(k,b)
   archive=buf.getvalue()
   if sum(map(len,artifacts.values()))+len(archive)>MAX_SESSION_OUTPUT_BYTES:raise ValueError('release_size_limit')
   with session.lock:session.release.update(artifacts);session.release['archive.zip']=archive
  stage(session,'release-generation','completed' if approved else 'unavailable')
  update(session,status='completed',releaseApproved=approved,finishedAt=time.time(),safeSummary='Internal release checks passed; synthetic use only.' if approved else 'Candidate processed; release withheld because verification or model readiness is incomplete.')
 except Exception:
  with session.lock:session.release.clear()
  failure_code={'model_initialization':'MODEL_UNAVAILABLE','verification':'VERIFICATION_FAILED'}.get(phase,'PROCESSING_FAILED')
  if phase=='verification':stage(session,'verification','failed')
  update(session,status='failed',releaseApproved=False,failureCode=failure_code,finishedAt=time.time(),safeSummary='Processing failed; no release is available.')
 finally:entries.clear()
@app.post('/api/run/practice')
def practice(request:Request):
 session=request.state.shield_session
 begin(session)
 def work():
  try:run(list(directory_entries(KIT/'dev'/'input')),session)
  except Exception:
   with session.lock:session.release.clear()
   update(session,status='failed',releaseApproved=False,failureCode='INPUT_UNAVAILABLE',safeSummary='Practice input unavailable.')
 threading.Thread(target=work,daemon=True).start();return current(request)
@app.post('/api/run/upload')
async def upload(request:Request):
 session=request.state.shield_session
 begin(session)
 try:
  ct=request.headers.get('content-type','')
  if not ct.lower().startswith('multipart/form-data;') or '\r' in ct or '\n' in ct:raise ValueError('multipart_required')
  body=bytearray()
  async for chunk in request.stream():
   if len(body)+len(chunk)>MAX_BYTES:raise ValueError('size_limit')
   body.extend(chunk)
  # Avoid Starlette UploadFile disk spooling; bounded parser runs entirely in memory.
  msg=BytesParser(policy=policy.default).parsebytes(('Content-Type: '+ct+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body);body.clear()
  if not msg.is_multipart() or msg.defects:raise ValueError('invalid_multipart')
  entries=[];total=0
  for p in msg.iter_parts():
   if p.defects or p.is_multipart() or p.get_param('name',header='content-disposition')!='files' or not p.get_filename():raise ValueError('invalid_part')
   data=p.get_payload(decode=True);name=safe_path(p.get_filename());total+=len(data)
   if total>MAX_BYTES or len(entries)>=MAX_FILES:raise ValueError('size_limit')
   entries.append((name,data))
  if len(entries)==1 and entries[0][0].lower().endswith('.zip'):entries=unzip(entries[0][1])
  if not entries or len({_safe_input_path(k) for k,_ in entries})!=len(entries):raise ValueError('duplicate_or_empty')
  threading.Thread(target=run,args=(sorted(entries),session),daemon=True).start();return current(request)
 except Exception:
  with session.lock:session.release.clear()
  update(session,status='failed',releaseApproved=False,finishedAt=time.time(),safeSummary='Import rejected. No release available.');raise HTTPException(400,'Import rejected') from None

def released(session):
 with session.lock:
  if not session.state.get('releaseApproved'):raise HTTPException(409,'No approved release')
  return dict(session.release)
@app.get('/api/release/files')
def inventory(request:Request):
 return [{'path':k,'size':len(v)} for k,v in sorted(released(request.state.shield_session).items()) if k.startswith('sanitized/')]
def selected(session,path):
 data=released(session)
 if not path.startswith('sanitized/') or path not in data:raise HTTPException(404,'File not found')
 return data[path]
@app.get('/api/release/preview')
def preview(request:Request,path:str):
 b=selected(request.state.shield_session,path)
 if len(b)>5*1024*1024:raise HTTPException(413,'Preview too large')
 t=b.decode('utf-8');ext=PurePosixPath(path).suffix.lower()
 if ext in ('.csv','.tsv'):
  rows=list(csv.reader(io.StringIO(t),delimiter='\t' if ext=='.tsv' else ','));return {'kind':'table','columns':rows[0] if rows else [],'rows':rows[1:]}
 return {'kind':'text','text':t}
def response(b,name):return Response(b,media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{name}"'})
@app.get('/api/release/download')
def download(request:Request,path:str):return response(selected(request.state.shield_session,path),'sanitized'+PurePosixPath(path).suffix)
@app.get('/api/release/artifact/{kind}')
def artifact(request:Request,kind:str):
 data=released(request.state.shield_session);key={'archive':'archive.zip','report':'report.json','records':'records.jsonl'}.get(kind)
 if not key:raise HTTPException(404,'Unknown artifact')
 return response(data[key],key)
@app.get('/api/release/identities')
def identities(request:Request):
  c=Counter();unresolved=0
  for line in released(request.state.shield_session)['records.jsonl'].splitlines():
    r=json.loads(line)
    if r.get('patient'):c[r['patient']]+=1
    else:unresolved+=1
  return {'identities':[{'pseudonymousId':k,'linkedRecordCount':v} for k,v in sorted(c.items())],'unresolvedCount':unresolved}

@app.get('/api/run/findings')
def findings(request:Request):
  session=request.state.shield_session
  with session.lock:
    return {'findings': session.state.get('detailedFindings', [])}

# Existing compiled UI: same-origin deployment, no Node or PowerShell required to start.
DIST=ROOT/'frontend'/'dist'
if (DIST/'index.html').is_file():
 app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
 @app.get('/{path:path}',include_in_schema=False)
 def frontend(path:str):
  if path.startswith('api/') or path=='api':raise HTTPException(404,'Not found')
  if path=='favicon.svg':return FileResponse(DIST/'favicon.svg')
  if path and '.' in PurePosixPath(path).name:raise HTTPException(404,'Not found')
  return FileResponse(DIST/'index.html')
