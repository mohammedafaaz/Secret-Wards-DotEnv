#!/usr/bin/env python3
"""Organizer entrypoint. No web server, no network, no raw intermediate files."""
import argparse,os,stat,sys
from pathlib import Path
from sheild.engine import run_pipeline,directory_entries,load_model

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--diagnostic-rules-only',action='store_true',help='Local diagnostic only; not official evaluation');a=p.parse_args()
 try:
  input_path=Path(a.input)
  try:input_stat=input_path.lstat()
  except OSError:
   print('ERROR INVALID_INPUT_DIRECTORY',file=sys.stderr);return 1
  if not stat.S_ISDIR(input_stat.st_mode) or stat.S_ISLNK(input_stat.st_mode) or bool(getattr(input_stat,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400)):
   print('ERROR INVALID_INPUT_DIRECTORY',file=sys.stderr);return 1
  inp,out=input_path.resolve(),Path(a.output).resolve()
  if inp==out or inp in out.parents or out in inp.parents or (out.exists() and any(out.iterdir())):
   print('ERROR UNSAFE_OUTPUT_DIRECTORY',file=sys.stderr);return 1
  secret=os.environ.get('RAKSHA_SECRET')
  if not secret:
   print('ERROR SECRET_MISSING',file=sys.stderr);return 1
  try:model=load_model(required=not a.diagnostic_rules_only) if not a.diagnostic_rules_only else None
  except Exception:
   print('ERROR MODEL_UNAVAILABLE',file=sys.stderr);return 1
  run_pipeline(directory_entries(inp),out,secret,model)
  print('Processing complete'+(' (rules-only diagnostic)' if a.diagnostic_rules_only else ''));return 0
 except OSError:
  print('ERROR OUTPUT_WRITE_FAILED',file=sys.stderr);return 1
 except Exception:
  print('ERROR PROCESSING_FAILED',file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
