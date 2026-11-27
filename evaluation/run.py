"""Run synthetic holdouts and report literal leakage, utility and pairwise linkage. Not official scoring."""
import argparse,base64,collections,hashlib,itertools,json,os,re,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def measure(root,out):
 truth=json.loads((root/'truth.json').read_text());rep=json.loads((out/'report.json').read_text());mapping={r['input_sha256']:r['output'] for r in rep['files']};recs={}
 for l in (out/'records.jsonl').read_text().splitlines():
  x=json.loads(l);recs.setdefault(x['file'],x['patient'])
 leak=total=keep=ptotal=quarantine=expected=unexpected=0;linked=[]
 for r in truth:
  f=root/'input'/r['file'];name=mapping[hashlib.sha256(f.read_bytes()).hexdigest()]
  if r['quarantine']:
   expected+=1;quarantine+=name is None;continue
  if not name:
   unexpected+=1;total+=len(r['pii']);ptotal+=len(r['preserve']);linked.append((r['person'],None));continue
  text=(out/name).read_text(encoding='utf-8');expanded=text
  for m in re.finditer(r'\b[A-Za-z0-9+/]{24,}={0,2}',text):
   try:expanded+='\n'+base64.b64decode(m[0]+'='*(-len(m[0])%4)).decode('utf-8')
   except (ValueError,UnicodeError):pass
  leak+=sum(x.casefold() in expanded.casefold() for x in r['pii']);total+=len(r['pii']);keep+=sum(x in text for x in r['preserve']);ptotal+=len(r['preserve']);linked.append((r['person'],recs.get(name)))
 tp=fp=fn=0
 for (a,x),(b,y) in itertools.combinations(linked,2):
  same=bool(x and x==y);tp+=a==b and same;fp+=a!=b and same;fn+=a==b and not same
 return {'files_total':len(truth),'files_sanitized':sum(not r['quarantine'] and bool(mapping.get(hashlib.sha256((root/'input'/r['file']).read_bytes()).hexdigest())) for r in truth),'files_quarantined':quarantine,'pii_leaked':leak,'pii_tested':total,'clinical_kept':keep,'clinical_tested':ptotal,'expected_quarantine':expected,'correct_quarantine':quarantine,'unexpected_quarantine':unexpected,'false_merge_pairs':fp,'link_precision':tp/(tp+fp) if tp+fp else None,'link_recall':tp/(tp+fn) if tp+fn else None,'timing':rep['timing'],'resources':rep['resources']}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data',required=True);p.add_argument('--rules-only',action='store_true');a=p.parse_args()
 with tempfile.TemporaryDirectory(prefix='sheild-eval-') as work:
  for kind in 'ABC':
   root=Path(a.data)/kind;out=Path(work)/kind;cmd=[sys.executable,str(ROOT/'main.py'),'--input',str(root/'input'),'--output',str(out)];cmd+=['--diagnostic-rules-only'] if a.rules_only else []
   subprocess.run(cmd,env={**os.environ,'RAKSHA_SECRET':'synthetic-evaluation-only'},check=True,cwd=ROOT,capture_output=True)
   validation=subprocess.run([sys.executable,str(ROOT/'Secret-Wards-ToolKit-main'/'validate_output.py'),'--input',str(root/'input'),'--output',str(out)],check=True,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
   if 'CONTRACT OK' not in validation.stdout:raise RuntimeError(f'{kind}_output_contract_failed')
   metrics=measure(root,out);metrics['output_contract_valid']=True
   print(kind,json.dumps(metrics))
