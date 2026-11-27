"""New adversarial regression cases. Candidate stub tests arbitration only, not CRF inference."""
import csv, datetime as dt, io, json, zipfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import backend.app as bridge
from sheild.engine import Engine,run_pipeline
from sheild.verify import verify

@pytest.fixture
def client():
 bridge.session_store.clear()
 with TestClient(bridge.app) as c:yield c
 bridge.session_store.clear()

def client_session(client):
 client.get('/api/run')
 return bridge.session_store.peek(client.cookies.get(bridge.SESSION_COOKIE))

@pytest.mark.parametrize('address', ['Address (attendant): C/O Arvin Selvek, Ward 17','Address (residence): Ward 21','Address: 18 Novel Avenue','Pata: Ward 88','पता: नई गली 28'])
def test_address_labels_preserve_clinical_ward(address):
 result=Engine('synthetic').clean_text(address+'\nWard: 7 (Medicine)\nC/O chest pain\n')
 assert result.splitlines()[0].endswith('[REDACTED]');assert 'Ward: 7 (Medicine)' in result and 'C/O chest pain' in result

def test_model_cross_line_candidate_is_rejected():
 text='Patient Name: Mira Solvek\nW/o Synthetic Relative\nAddress: 17 Example Road\n'
 class OverlappingCandidate:
  def spans(self,t):
   a=t.index('Synthetic');b=t.index(':',a)
   return [{'start':a,'end':b,'label':'RELATIVE'}]
 assert Engine('synthetic',OverlappingCandidate()).clean_text(text)=='Patient Name: [REDACTED]\nW/o [REDACTED]\nAddress: [REDACTED]\n'

@pytest.mark.parametrize(('text','pii','clinical'),[
 ('Patient Mira Solvek lives at Juniper Crescent. BP 118/76; Metformin 500 mg.',['Mira Solvek','Juniper Crescent'],['BP 118/76','Metformin 500 mg']),
 ('Patient Mira Solvek entered from Silver Fern Arcade; contact person: Vasha Menon. Continue iron 30 mg daily.',['Mira Solvek','Silver Fern Arcade','Vasha Menon'],['Continue iron 30 mg']),
 ('रोगी तविरा वोरन; निवास स्थल: चमेली पथ। नाड़ी 72 bpm; मेटफॉर्मिन 500 mg.',['तविरा वोरन','चमेली पथ'],['नाड़ी 72 bpm','मेटफॉर्मिन 500 mg']),
])
def test_multilingual_narrative_names_and_locations_preserve_clinical(text,pii,clinical):
 result=Engine('synthetic').clean_text(text)
 assert all(surface not in result for surface in pii)
 assert all(probe in result for probe in clinical)

def test_patient_mentions_are_not_linkage_evidence_for_relatives():
 text='रोगी तविरा वोरन को परिजन सवेन निलव लाए; BP 118/76.'
 cleaned=Engine('synthetic').clean_text(text)
 assert 'तविरा वोरन' not in cleaned and 'सवेन निलव' not in cleaned
 assert 'BP 118/76' in cleaned

def test_clinician_name_is_preserved_in_narrative_location_note():
 text='Patient: Mira Solvek; consultant Dr. Renu Sethi reviewed; residence is Juniper Crescent.'
 cleaned=Engine('synthetic').clean_text(text)
 assert 'Mira Solvek' not in cleaned and 'Juniper Crescent' not in cleaned
 assert 'Dr. Renu Sethi' in cleaned

def test_administrative_geography_is_preserved_for_medical_utility_priority():
 source={'patient_name':'Mira Solvek','hospital':'Synthetic Hospital','district':'North Example','state':'Example State','diagnosis':'Diabetes mellitus','medicine':'Metformin 500 mg','result':120.5}
 output={};_,documents=run_pipeline([('geo.json',json.dumps(source).encode())],output,'synthetic',None)
 sanitized=json.loads(output[documents[0].output])
 assert sanitized['hospital']=='Synthetic Hospital' and sanitized['district']=='North Example' and sanitized['state']=='Example State'
 assert sanitized['diagnosis']=='Diabetes mellitus' and sanitized['medicine']=='Metformin 500 mg' and sanitized['result']==120.5

def test_street_column_suppresses_house_and_locality_without_losing_clinical_fields():
 source=('Patient Name,MRN,Street,City,District,Diagnosis,Medicine\n'
         'Mira Solvek,MR-123456,"H.No. 180, Mohalla Subhash Nagar",Gopaldih,Sitapur,Type 2 diabetes,Metformin 500 mg\n').encode()
 output={};_,documents=run_pipeline([('legacy.csv',source)],output,'synthetic',None)
 rows=list(csv.DictReader(io.StringIO(output[documents[0].output].decode('utf-8'))))
 assert rows[0]['Street']=='[REDACTED]'
 assert 'H.No. 180' not in output[documents[0].output].decode('utf-8')
 assert rows[0]['Diagnosis']=='Type 2 diabetes' and rows[0]['Medicine']=='Metformin 500 mg'

def test_slash_dates_infer_one_convention_preserve_interval():
 entries=[('case.txt',b'Patient Name: Mira Solvek\nMRN: ZZ-987654\nAdmission: 09/26/2026\nDischarge: 10/08/2026\n')];out={};run_pipeline(entries,out,'synthetic',None)
 text=out['sanitized/case.txt'].decode();lines=dict(l.split(': ',1) for l in text.splitlines() if ': ' in l)
 a,b=(dt.datetime.strptime(lines[k],'%m/%d/%Y').date() for k in ('Admission','Discharge'))
 assert (b-a).days==12

def test_facility_local_id_collision_no_merge():
 entries=[('a.json',b'{"hospital":"Alpha Facility","patient_name":"Mira Solvek","MRN":"MR-123456"}'),('b.json',b'{"hospital":"Beta Facility","patient_name":"Mira Solvek","MRN":"MR-123456"}')];out={};run_pipeline(entries,out,'synthetic',None)
 rows=[json.loads(l) for l in out['records.jsonl'].splitlines()];assert len(rows)==2 and rows[0]['patient']!=rows[1]['patient']

def test_clinical_probe_in_other_record_not_enough():
 entries=[('a.json',b'{"patients":[{"patient_name":"Mira Solvek","MRN":"MR-111111","medicine":"Drug A 12 mg"},{"patient_name":"Nira Telvak","MRN":"MR-222222","medicine":"Drug B 19 mg"}]}')];out={};r,d=run_pipeline(entries,out,'synthetic',None)
 v=json.loads(out['sanitized/a.json']);v['patients'][0]['medicine'],v['patients'][1]['medicine']=v['patients'][1]['medicine'],v['patients'][0]['medicine'];out['sanitized/a.json']=json.dumps(v).encode()
 result=verify(entries,out,d);assert not result['approved'] and result['findings']['clinical_path_changed']==2

def test_record_claim_wrong_row_is_rejected():
 entries=[('x.csv',b'Patient Name,MRN,Medicine\nMira Solvek,MR-111111,Drug A\nNira Telvak,MR-222222,Drug B\n')];out={};r,d=run_pipeline(entries,out,'synthetic',None);rows=[json.loads(l) for l in out['records.jsonl'].splitlines()];rows[0]['patient'],rows[1]['patient']=rows[1]['patient'],rows[0]['patient'];out['records.jsonl']=('\n'.join(json.dumps(x) for x in rows)+'\n').encode();result=verify(entries,out,d);assert not result['approved'] and result['findings']['missing_pseudonym']==2

@pytest.mark.parametrize('names',[('A.txt','a.txt'),('café.txt','cafe\u0301.txt'),('a.txt','../bad.txt')])
def test_duplicate_or_unsafe_archive_paths(client,names):
 b=io.BytesIO()
 with zipfile.ZipFile(b,'w') as z:
  for name in names:z.writestr(name,'test')
 assert client.post('/api/run/upload',files=[('files',('synthetic.zip',b.getvalue()))]).status_code==400
 assert client.get('/api/release/files').status_code==409

def test_busy_run_cannot_be_overwritten(client):
 session=client_session(client);bridge.begin(session);response=client.post('/api/run/upload',files=[('files',('synthetic.txt',b'clinical'))]);assert response.status_code==409;assert session.state['status']=='queued'

def test_one_server_serves_compiled_website(client):
 for route in ('/','/workspace','/engine','/research','/integrity','/release'):
  r=client.get(route);assert r.status_code==200 and 'Shield' in r.text and 'Sheild' not in r.text
 assert client.get('/api/nonexistent').status_code==404
 assert client.get('/api/health').json()['team']=='DOTENV'
 assert client.get('/api/release/files').status_code==409

def test_date_offset_rejects_original_birth_date():
 engine=Engine('synthetic-offset');d=dt.date(1990,1,15);key='synthetic-patient';first=engine.choose_offset(key,[d]);collision=d+dt.timedelta(days=first);engine.forbidden_dates.add(collision);second=engine.choose_offset(key,[d]);assert second!=first and second!=0;assert d+dt.timedelta(days=second)!=collision

def test_bare_age_label_is_generalized():
 text=Engine('synthetic').clean_text('Age: 43\nBP 120/80\nHistory: pain for 4 years\n');assert 'Age: 40-59' in text and 'BP 120/80' in text and 'pain for 4 years' in text
