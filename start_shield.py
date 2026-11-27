"""Single-process shield launcher. No shell activation, Node, or PowerShell needed."""
from __future__ import annotations
import argparse, os, socket, subprocess, sys, time, urllib.request, venv, webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
VENV=ROOT/'.venv312'

def venv_python():return VENV/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def probe(exe,code):
 try:return subprocess.run([str(exe),'-c',code],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=25).returncode==0
 except (OSError,subprocess.TimeoutExpired):return False

def check_interpreter(exe):return probe(exe,'import sys; assert (3,12)<=sys.version_info[:2]<=(3,14)')
def prepare(install):
 exe=venv_python()
 if not check_interpreter(exe):
  if not install:raise RuntimeError('A valid .venv312 Python environment is missing.')
  if VENV.exists():
   backup=ROOT/f'.venv312.invalid-{time.time_ns()}'
   VENV.rename(backup);print(f'Old invalid environment moved to {backup.name}.',flush=True)
  print('Creating local Python environment...',flush=True);venv.EnvBuilder(with_pip=True).create(VENV)
 code="import fastapi,uvicorn,rapidfuzz,psutil; from sheild.engine import load_model; load_model(required=True)"
 if not probe(exe,code):
  if not install:raise RuntimeError('Required runtime or trained CRF model could not be loaded.')
  print('Installing required Python packages (internet needed on first setup)...',flush=True)
  subprocess.run([str(exe),'-m','pip','install','--disable-pip-version-check','-r',str(ROOT/'backend/requirements.txt')],cwd=ROOT,check=True)
  if not probe(exe,code):raise RuntimeError('The model or dependencies failed startup validation. Check the installation output above.')
 return exe

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');p.add_argument('--no-install',action='store_true');p.add_argument('--no-browser',action='store_true');p.add_argument('--port',type=int,default=8000);a=p.parse_args()
 if not ((3,12)<=sys.version_info[:2]<=(3,14)):
  print('Python 3.12 (recommended), 3.13 or 3.14 is required. Install Python 3.12 x64 and rerun START_SHIELD.cmd.');return 1
 if not (ROOT/'frontend/dist/index.html').is_file():print('Compiled website is missing. Extract the complete project archive.');return 1
 try:
  exe=prepare(not a.no_install)
  if a.check:print('shield startup prerequisites and trained model validated.');return 0
  if not 1024<=a.port<=65535:raise RuntimeError('Choose a port between 1024 and 65535.')
  with socket.socket() as s:
   try:s.bind(('127.0.0.1',a.port))
   except OSError:raise RuntimeError(f'Port {a.port} is already in use. Close the previous shield window or choose a different port.') from None
  url=f'http://127.0.0.1:{a.port}'
  env=dict(os.environ);env.pop('SHEILD_RULES_DIAGNOSTIC',None);env['SHIELD_WEB_PORT']=str(a.port);env['PYTHONUTF8']='1';env['PYTHONNOUSERSITE']='1'
  proc=subprocess.Popen([str(exe),'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port',str(a.port),'--no-access-log'],cwd=ROOT,env=env)
  try:
   opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
   for _ in range(100):
    if proc.poll() is not None:raise RuntimeError('Server stopped during startup.')
    try:
     with opener.open(url+'/api/health',timeout=.5) as res:
      if res.status==200:break
    except OSError:time.sleep(.1)
   else:raise RuntimeError('Server did not become ready.')
   print(f'\nDOTENV | shield is running at {url}\nKeep this window open. Press Ctrl+C to stop.',flush=True)
   if not a.no_browser:webbrowser.open(url)
   return proc.wait()
  except KeyboardInterrupt:return 0
  finally:
   if proc.poll() is None:
    proc.terminate()
    try:proc.wait(timeout=5)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
 except (RuntimeError,OSError,subprocess.CalledProcessError) as e:
  print('Startup failed: '+str(e),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
