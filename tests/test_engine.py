import json,os,hashlib,datetime as dt
from sheild.engine import run_pipeline,Engine,Record,Evidence
from sheild.verify import verify

def fixture():
 return [('one.csv',b'Patient Name,MRN,Mobile,DOB,Age,Medicine,Admission Date,Discharge Date\nExample Narela,ZZ-123456,8765432109,1980-02-14,46,Metformin 500 mg,2026-01-10,2026-01-15\n'),('two.json',json.dumps({'patient_name':'Example Narela','MRN':'ZZ-123456','phone':'8765432109','diagnosis':'Wilson disease','medicine':'Metformin 500 mg','bp':'120/80','age':46}).encode())]
def test_same_identity_and_secret_rotation():
 a={};b={};c={};entries=fixture();ra,docs=run_pipeline(entries,a,'one',None);run_pipeline(entries,b,'one',None);run_pipeline(entries,c,'two',None)
 for k in a:
  if k!='report.json':assert a[k]==b[k]
 rows=[json.loads(x) for x in a['records.jsonl'].splitlines()];assert len(rows)==2 and rows[0]['patient']==rows[1]['patient']
 assert c['records.jsonl']!=a['records.jsonl'];assert b'Example Narela' not in a['sanitized/one.csv'];assert b'Metformin 500 mg' in a['sanitized/one.csv'];assert b'8765432109' not in a['sanitized/two.json']
 import csv,io
 row=list(csv.reader(io.StringIO(a['sanitized/one.csv'].decode())))[1];assert (dt.date.fromisoformat(row[-1])-dt.date.fromisoformat(row[-2])).days==5
 assert verify(entries,a,docs)['approved']
def test_conflicting_identities():
 entries=[('a.json',b'{"patient_name":"Same Name","father_name":"Same Relative","phone":"8765432109","dob":"1970-01-01","aadhaar":"123456789012"}'),('b.json',b'{"patient_name":"Same Name","father_name":"Same Relative","phone":"8765432109","dob":"1990-01-01","aadhaar":"123456789013"}')];out={};run_pipeline(entries,out,'test',None);rows=[json.loads(x) for x in out['records.jsonl'].splitlines()];assert rows[0]['patient']!=rows[1]['patient']
def test_name_and_relative_link_without_other_identifiers():
 entries=[('a.json',b'{"patient_name":"Mavini Talvek","father_name":"Nirvan Vek"}'),('b.json',b'{"patient_name":"Mavini Talvek","father_name":"Nirvan Vek"}')];out={};run_pipeline(entries,out,'test',None);rows=[json.loads(x) for x in out['records.jsonl'].splitlines()];assert rows[0]['patient'] and rows[0]['patient']==rows[1]['patient']
def test_inline_address_does_not_consume_following_clinical_values():
 entries=[('note.txt',b'Patient: Kivara Meloth\nAddress: Tamarind Mews. BP 118/76; Metformin 500 mg.')];out={};run_pipeline(entries,out,'test',None);safe=out['sanitized/note.txt'].decode('utf-8');assert 'Kivara Meloth' not in safe and 'Tamarind Mews' not in safe and 'BP 118/76' in safe and 'Metformin 500 mg' in safe
def test_clinical_and_malformed():
 entries=[('note.txt','Patient: Mavini Talvek\nC/O chest pain\nK/C/O DM2 x 8 yrs\nDr. Mavini Talvek\nBP 120/80\nMetformin 500 mg\nFather: Dr. Nirvan Vek'.encode()),('bad.json',b'{"x":1,"x":2}'),('bad.csv',b'a,b\n1,2,3\n')];out={};report,docs=run_pipeline(entries,out,'test',None);assert report['counts']['files_quarantined']==2;t=out['sanitized/note.txt'].decode();assert 'C/O chest pain' in t and 'K/C/O DM2 x 8 yrs' in t and 'Dr. Mavini Talvek' in t and 'Metformin 500 mg' in t and 'Nirvan Vek' not in t
def test_gate_blocks_tampering():
 entries=fixture();out={};r,docs=run_pipeline(entries,out,'test',None);out['sanitized/one.csv']+=b'\nExample Narela,8765432109';assert not verify(entries,out,docs)['approved']
