"""Independent synthetic challenge fixtures, NOT organizer hidden data or training data."""
import argparse,base64,csv,json,random
from pathlib import Path

def build(root,kind,count,seed):
 rng=random.Random(seed);root=Path(root);inp=root/'input';inp.mkdir(parents=True,exist_ok=False);truth=[];register=[]
 names=['Veyon Talmek','Nirvani Kovesh','Zevira Dalmor','Rivaan Hestik','Mavini Solvek','Tevrin Narev','Arovi Telvan','Zarvik Melnor','Ovika Darsen','Seyran Tavik']
 dev=['वेयोन तालमेक','निर्वानी कोवेश','ज़ेविरा डालमोर','रिवान हेस्टिक','माविनी सोलवेक','तेवरिन नारेव','आरोवी तेलवान','ज़ारविक मेल्नोर','ओविका दार्सेन','सेयरान ताविक']
 for i in range(count):
  person=i//4;name=names[person%len(names)]+f' {person:04d}';hname=dev[person%len(dev)]+f' {person:04d}';relative=f'Kalpit Kin{person:04d}';phone='8'+str(100000000+person);local=f'QH-{100000+person}';age=25+person%70;dob=f'{2026-age}-03-11';med='Metformin 500 mg';bp='120/80';diag='Wilson disease' if person%17==0 else 'Type 2 diabetes';can=f'SyntheticWitness {rng.getrandbits(48):012x}'
  register.append({'person':person,'name':name,'age':age,'district':'Test District','phone':phone}) if i%4==0 else None
  path=f'case_{i:05d}.json';preserve=[med,bp,diag];pii=[name,relative,phone,local];date='2026-09-12';end='2026-09-17'
  if kind=='C' and i%19==0:
   path=f'broken_{i:05d}.json';raw=b'{"patient": ';truth.append({'file':path,'quarantine':True});(inp/path).write_bytes(raw);continue
  if i%4==0:
   path=f'case_{i:05d}.csv';buf=__import__('io').StringIO();w=csv.writer(buf);w.writerow(['Beneficiary','Facility Person Reference','Guardian','Sampark Sutra','Completed Years','Janm Dinank','Medicine','BP','Diagnosis','Admission Date','Discharge Date']);w.writerow([name,local,relative,phone,age,dob,med,bp,diag,date,end]);raw=buf.getvalue().encode('utf-8-sig')
  elif i%4==1:
   obj={'patient':{'name':name,'relative':relative,'phone':phone,'MRN':local,'age':age,'DOB':dob},'medicine':med,'bp':bp,'diagnosis':diag,'admission_date':date,'discharge_date':end}
   if kind=='B':obj['source_path']=f'/records/{name}/{local}';obj['attachment']={'contentType':'text/plain','data':base64.b64encode(f'Witnessed by {can}, phone {phone}'.encode()).decode()};pii.append(can)
   raw=json.dumps(obj,ensure_ascii=False).encode()
  elif i%4==2:
   path=f'case_{i:05d}.txt';txt=f'Patient Name: {name}\nMRN: {local}\nGuardian: {relative}\nMobile: {phone}\nAge: {age} yrs\nDOB: {dob}\nC/O chest pain\n{med}\nBP {bp}\nDiagnosis: {diag}\nAdmission: {date}\nDischarge: {end}\n';raw=txt.encode('utf-16' if kind=='C' else 'utf-8')
  else:
   path=f'case_{i:05d}.txt';txt=f'नाम: {hname}\nपिता: {relative}\nMRN: {local}\nमोबाइल: {phone}\nआयु: {age} वर्ष\n{med}\nBP {bp}\nDiagnosis: {diag}\n';pii=[hname,relative,phone,local];raw=txt.encode()
  (inp/path).write_bytes(raw);truth.append({'file':path,'person':person,'pii':pii,'preserve':preserve,'quarantine':False,'age':age})
 (root/'truth.json').write_text(json.dumps(truth,ensure_ascii=False,indent=2),encoding='utf-8');(root/'registry.json').write_text(json.dumps(register,indent=2),encoding='utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--scale',type=int,default=1);a=p.parse_args()
 for kind,n,seed in [('A',200,11039),('B',500,22073),('C',1000,33091)]:build(Path(a.out)/kind,kind,n*a.scale,seed)
