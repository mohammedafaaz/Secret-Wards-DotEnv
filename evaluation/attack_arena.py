"""Synthetic practice-only A1–A7 approximations. NOT the organizer evaluator.
Ground truth is used only to select/scoring units and determine the true registry
person. This module is never imported by the evaluated application.
"""
from __future__ import annotations
import argparse,base64,csv,datetime as dt,hashlib,io,json,re,unicodedata
from collections import Counter,defaultdict
from functools import lru_cache
from pathlib import Path

D=re.compile(r'(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4})(?!\d)')
PSN=re.compile(r'\bPSN-[0-9a-f]{20}\b')
def norm(s):
 return ' '.join(''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in unicodedata.normalize('NFKC',str(s))).casefold().split())
def fields(value,key=''):
 if isinstance(value,dict):
  for k,v in value.items():yield from fields(v,str(k))
 elif isinstance(value,list):
  for v in value:yield from fields(v,key)
 elif value is not None:yield key,str(value)
def date_values(t,hint='dmy'):
 dates=[]
 for m in D.finditer(t):
  fmts=['%Y-%m-%d','%m/%d/%Y','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y'] if hint=='mdy' else ['%Y-%m-%d','%d/%m/%Y','%m/%d/%Y','%d-%m-%Y','%d.%m.%Y']
  for fmt in fmts:
   try:dates.append(dt.datetime.strptime(m[0],fmt).date());break
   except ValueError:pass
 return dates
def pointer(v,loc):
 for k in loc.lstrip('/').split('/'):
  k=k.replace('~1','/').replace('~0','~');v=v[int(k)] if isinstance(v,list) else v[k]
 return v
def unit_text(path,loc,meta,raw=False):
 if not path.is_file():return '',[]
 try:
  t=path.read_bytes().decode(meta.get('encoding','utf-8') if raw else 'utf-8-sig');f=[]
  if loc.startswith('row:'):
   rows=list(csv.DictReader(io.StringIO(t),delimiter=meta.get('delimiter',',') or ','));v=rows[int(loc[4:])];f=list(fields(v));t='\n'.join(f'{k}: {v}' for k,v in f)
  elif loc.startswith('/') or path.suffix=='.json':
   v=json.loads(t);v=pointer(v,loc) if loc.startswith('/') else v;f=list(fields(v));t=json.dumps(v,ensure_ascii=False)+'\n'+'\n'.join(f'{k}: {v}' for k,v in f)
  else:
   f=[tuple(line.split(':',1)) for line in t.splitlines() if ':' in line]
  return t,f
 except (ValueError,KeyError,IndexError,UnicodeError,LookupError):return '',[]
def extract(text,f,hint):
 t=norm(text);ages=[];genders=set();ids=set();names=[]
 for k,v in f:
  k=re.sub(r'[^\w]','',norm(k));v=norm(v)
  if k in {'age','agesex','ageband','age_band','umar','आयु','उम्र','completedyears'} or k.endswith('ageband'):
   m=re.match(r'(\d{1,3})(?:\s*-\s*(\d{1,3})|(\+))?',v)
   if m:ages.append((int(m[1]),int(m[2]) if m[2] else 125 if m[3] else int(m[1])))
  if k in {'gender','sex','ling','लिंग'}:
   if v in {'m','male','पुरुष'}:genders.add('m')
   if v in {'f','female','महिला'}:genders.add('f')
  if k in {'uhid','mrn','patientid','patientref','patient_ref','regno','registrationno'} and v and 'redacted' not in v:ids.add(v)
  if k in {'name','patientname','patient','naam','नाम','beneficiary'} and v and 'redacted' not in v:names.append(v)
 for m in re.finditer(r'(?<!\d)(\d{1,3})(?:\s*-\s*(\d{1,3})|(\+))?\s*(?:yrs?\b|years?\b|वर्ष|/\s*[mf]\b)',t):
  before=t[max(0,m.start()-12):m.start()]
  if re.search(r'(?:\bx|for|since|h/o)\s*$',before):continue
  ages.append((int(m[1]),int(m[2]) if m[2] else 125 if m[3] else int(m[1])))
 dates=date_values(text,hint)
 return {'text':t,'ages':ages,'genders':genders,'dates':dates,'ids':ids,'names':names}
def pool(es):
 return {'text':'\n'.join(e['text'] for e in es),'ages':[a for e in es for a in e['ages']], 'genders':set().union(*(e['genders'] for e in es)), 'dates':[d for e in es for d in e['dates']], 'ids':set().union(*(e['ids'] for e in es)), 'names':[n for e in es for n in e['names']]}
@lru_cache(maxsize=32768)
def boundary_value(v):return " "+re.sub(r"[^\w]+"," ",v).strip()+" "
def match(e,registry):
 # Generic filtering, skipping empty filters. Literal matching only, no official
 # transliteration or exhaustive masked-digit, PIN-prefix or age-drift logic.
 t=boundary_value(e['text']);cand=list(registry);observed={};cache={}
 def hit(v):
  if v not in cache:cache[v]=bool(v and len(v)>1 and boundary_value(v) in t)
  return cache[v]
 for key in ('phone','email','aadhaar_last4','district','tehsil','village','pin'):
  # Last4 alone is too common in medical numbers; require explicit masked context.
  if key=='aadhaar_last4':continue
  observed[key]={r[key] for r in registry if hit(r.get(key,''))}
 for key in ('phone','email','district','gender','age','tehsil','village','pin'):
  if key=='gender':subset=[r for r in cand if not e['genders'] or r['gender'] in e['genders']]
  elif key=='age':subset=[r for r in cand if not e['ages'] or any(a-1<=int(r['age'])<=b+2 for a,b in e['ages'])]
  else:subset=[r for r in cand if not observed[key] or r[key] in observed[key]]
  if subset:cand=subset
 weights={}
 for r in cand:
  n=r['name'].split();w=60 if hit(r['name']) else (8 if n and hit(n[0]) else 1)*(3 if len(n)>1 and hit(n[-1]) else 1)
  if hit(r.get('relative_name','')):w*=8
  weights[r['rid']]=w
 total=sum(weights.values());return {k:v/total for k,v in weights.items()} if total else {}
def transforms(s):
 for v in {s,s.lower(),re.sub(r'\D','',s)}:
  if not v:continue
  yield v.casefold();yield v[::-1].casefold();yield base64.b64encode(v.encode()).decode().casefold()
  for alg in ('md5','sha1','sha256','sha512'):yield hashlib.new(alg,v.encode()).hexdigest()
def run(kit,out,rotated):
 truth=json.loads((kit/'dev/truth/truth.json').read_text(encoding='utf-8'));registry=[{k:(v if k=='rid' else norm(v)) for k,v in r.items()} for r in csv.DictReader((kit/'dev/attacker/registry.csv').open(encoding='utf-8'))];byrid={r['rid']:r for r in registry}
 facts=[json.loads(l) for l in (kit/'dev/attacker/known_facts.jsonl').read_text(encoding='utf-8').splitlines()];people=truth['patients'];pids={p:v['rid'] for p,v in people.items()};
 def index(root):
  rep=json.loads((root/'report.json').read_text(encoding='utf-8'));mapping={x['input_sha256']:x['output'] for x in rep['files']};rec=defaultdict(dict)
  for l in (root/'records.jsonl').read_text(encoding='utf-8').splitlines():
   v=json.loads(l);rec[v['file']][v['loc']]=v.get('patient')
  return mapping,rec
 mapping,recs=index(out);mapping2,recs2=index(rotated)
 def getpid(rec,loc):
  if loc in rec:return rec[loc]
  while '/' in loc:
   loc=loc.rsplit('/',1)[0]
   if loc in rec:return rec[loc]
  return rec.get('doc')
 units=[];direct=set();raw_direct=set();originals=defaultdict(set);stable_dates=total_dates=stable_pids=total_pids=0;pid_set=set();inverted=set()
 for rel,meta in truth['files'].items():
  path=mapping.get(meta['sha256']);path2=mapping2.get(meta['sha256'])
  for loc,u in meta['units'].items():
   p=u.get('patient');rid=pids.get(p)
   if not rid:continue
   raw,rf=unit_text(kit/'dev/input'/rel,loc,meta,True);safe,sf=unit_text(out/path,loc,meta) if path else ('',[]);safe2,sf2=unit_text(rotated/path2,loc,meta) if path2 else ('',[])
   e=extract(safe,sf,meta.get('date_hint','dmy'));r=extract(raw,rf,meta.get('date_hint','dmy'));e2=extract(safe2,sf2,meta.get('date_hint','dmy'))
   pid=getpid(recs.get(path,{}),loc);pid2=getpid(recs2.get(path2,{}),loc)
   if pid and pid in safe:
    pid_set.add((p,pid));total_pids+=1;stable_pids+=pid==pid2
   else:pid=None
   if path and path2:
    for a,b in zip(e['dates'],e2['dates']):total_dates+=1;stable_dates+=a==b
   for entity in u['entities']:
    if entity['type'] not in {'PATIENT_NAME','PHONE','EMAIL','AADHAAR','AADHAAR_MASKED','ABHA_NUMBER','MRN','PAN','INSURANCE_ID'}:continue
    surface=norm(entity['surface']);originals[p].add(entity['surface']);
    if surface and (surface in norm(raw) or surface in norm(rel)):raw_direct.add(p)
    if surface and (surface in norm(safe) or surface in norm(path or '')):direct.add(p)
   units.append((p,rid,pid,e,r, bool(path)))
 for p,pid in pid_set:
  values=set(originals[p])|{byrid[pids[p]]['name'],byrid[pids[p]]['phone']}
  token=pid.casefold();core=token.removeprefix('psn-')
  if any(len(v)>=8 and (token==v or v.startswith(core) or core.startswith(v) or (v.isdigit() and v in core)) for s in values for v in transforms(s)):inverted.add(p)
 def attack(raw=False):
  profiles=defaultdict(list);owners=defaultdict(set);record=[]
  for i,(p,rid,pid,e,r,exists) in enumerate(units):
   if not raw and not exists:continue
   ev=r if raw else e;prob=match(ev,registry);record.append(prob.get(rid,0))
   key=('raw-id',sorted(ev['ids'])[0]) if raw and ev['ids'] else ('raw-name',sorted(ev['names'])[0]) if raw and ev['names'] else ('pid',pid) if not raw and pid else ('unit',i)
   profiles[key].append(ev);owners[key].add(rid)
  pp={k:pool(v) for k,v in profiles.items()};dist={k:match(v,registry) for k,v in pp.items()};identified={rid for k,ids in owners.items() for rid in ids if dist[k].get(rid,0)>=.5}
  # Known-fact attack: date/rare-condition/LOS matches; global offset recovery
  # is attempted only on high-confidence profiles with at least two agreeing targets.
  offsets=defaultdict(set)
  for fact in facts:
   rid=fact['rid'];dates=[dt.date.fromisoformat(d) for d in fact.get('visit_dates',[])]
   for k,e in pp.items():
    if dist[k].get(rid,0)>=.9:
     for d in dates:
      for x in e['dates']:
       delta=(x-d).days
       if abs(delta)<=366:offsets[delta].add(rid)
  shift=max(offsets,key=lambda k:len(offsets[k]),default=0) if offsets else 0
  if len(offsets.get(shift,set()))<2:shift=0
  targeted=[];decoy=0
  for fact in facts:
   rid=fact['rid'];dates={dt.date.fromisoformat(d) for d in fact.get('visit_dates',[])};condition=norm(fact.get('condition_hint',''));scores={};rare=bool(condition) and sum(condition in e['text'] for e in pp.values())<=3
   for k,e in pp.items():
    datehit=any((x-dt.timedelta(days=shift)) in dates for x in e['dates']);condhit=bool(condition and condition in e['text']);los=fact.get('length_of_stay',fact.get('los_days'))
    loshit=isinstance(los,int) and any(x+dt.timedelta(days=los) in set(e['dates']) for x in set(e['dates']))
    if not (datehit or condhit or loshit):continue
    w=dist[k].get(rid,0)*(int(datehit)+int(loshit)+(8 if rare else 1)*int(condhit))
    if fact.get('hospital') and norm(fact['hospital']) in e['text']:w*=2
    if w:scores[k]=w
   if rid in pids.values():targeted.append(sum(w for k,w in scores.items() if rid in owners[k])/sum(scores.values()) if scores else 0)
   elif scores:decoy+=1
  return {'A2_A3_mean_true_probability':sum(record)/len(record) if record else None,'A4_confident_profile_share':len(identified)/len(people),'A5_targeted_mean_probability':sum(targeted)/len(targeted) if targeted else None,'A5_decoy_matches':decoy,'A5_global_shift_recovered':bool(shift),'record_units':len(record),'profiles':len(pp)}
 raw=attack(True);safe=attack();raw['A1_literal_direct_share']=len(raw_direct)/len(people);safe['A1_literal_direct_share']=len(direct)/len(people);safe['A6_inversion_share']=len(inverted)/len({p for p,_ in pid_set}) if pid_set else None;safe['A7_stable_record_pseudonym_share']=stable_pids/total_pids if total_pids else None;safe['A7_stable_date_position_share']=stable_dates/total_dates if total_dates else None
 return {'scope':'synthetic practice-only approximation; literal, partial field extraction, no official score; A1 uses per-unit truth surfaces, A4 raw grouping heuristic, A7 aligned date positions not exact official metric','raw':raw,'sanitized':safe,'normalized':{k:safe[k]/raw[k] if raw[k] else None for k in ('A1_literal_direct_share','A2_A3_mean_true_probability','A4_confident_profile_share','A5_targeted_mean_probability')}}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--kit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--rotated',type=Path,required=True);a=p.parse_args();print(json.dumps(run(a.kit,a.output,a.rotated),indent=2))
