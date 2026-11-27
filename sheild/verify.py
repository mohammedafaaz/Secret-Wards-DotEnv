"""Independent conservative release checks. No organizer truth, models or training data."""
import base64,csv,hashlib,io,json,re,unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import unquote
from html import unescape

from dataclasses import dataclass

# Deliberately independent of the detector. These checks cover known patterns, not anonymity.
# Extended phone: standard 10-digit Indian mobile (with optional +91/0 prefix) plus bare 11-digit
# numbers starting [6-9] that may appear without a country-code prefix.
DIRECT=re.compile(r'(?<!\d)(?:\+?91[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)|(?<!\d)[6-9]\d{10}(?!\d)|(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)|\b[A-Z]{5}\d{4}[A-Z]\b|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}',re.I)
B64=re.compile(r'\b[A-Za-z0-9+/]{24,}={0,2}')
CLINICAL={'drug','medicine','medication','strength','dose','dosage','frequency','duration','test','loinc','unit','range','refrange','referencerange','result','bp','pulse','tempf','spo2','weightkg','diagnosis','procedure','code','doctor','refdoctor','referredby','consultant','physician'}
# Clinical measurement words that indicate a label is for clinical data, not a name field
CLINICAL_MEASURE={'temperature','temp','fever','bp','pulse','heart','rate','spo2','oxygen','saturation','weight','height','bmi','respiration','resp','pain','score','glucose','sugar','hba1c','cholesterol','creatinine','urea','potassium','sodium','hemoglobin','hb','wbc','rbc','platelet','inr','pt','aptt'}

@dataclass
class DetailedFinding:
    file_ref: str
    record_locator: str
    category: str
    reason: str
    suggested_action: str

def label(x):return re.sub(r'[^a-z0-9]','',x.casefold())
def fold(x):return ' '.join(unicodedata.normalize('NFKC',x).casefold().split())
def _independent_tokens(value):
  value=unicodedata.normalize('NFKC',str(value))
  value=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',value)
  return {part.casefold() for part in re.findall(r'[A-Za-z0-9]+|[\u0900-\u097f]+',value)}
def _independent_label_role(key,parents=(),resource=''):
  tokens=_independent_tokens(key)
  if tokens&{'doctor','clinician','practitioner','physician','consultant'}:return None
  if tokens&{'contact','reach','callback','phone','mobile','telephone','tel','sampark','संपर्क','मोबाइल','फोन','दूरभाष'}:return 'contact'
  if tokens&{'kin','guardian','relative','attendant','caregiver','father','mother','husband','wife','spouse','sister','brother','daughter','son','परिजन','रिश्तेदार','अभिभावक','पिता','माता','पति','पत्नी','पुत्र','पुत्री','भाई','बहन','साक्षी','rishtedaar','sambandhi'}:return 'relative'
  if tokens&{'family','household','परिवार','parivar'} and tokens&{'witness','member','सदस्य','relative','name','alias','signature','person','contact','साक्षी','व्यक्ति','संबंधी','परिजन','sakshi'}:return 'relative'
  if ('accompanying' in tokens and 'person' in tokens) or ('साथ' in tokens and tokens&{'व्यक्ति','परिजन','संबंधी','रिश्तेदार'}) or ('saath' in tokens and tokens&{'vyakti','rishtedaar','sambandhi'}):return 'relative'
  if resource not in {'Practitioner','Organization'} and 'name' in parents and tokens&{'text','given','family'}:return 'name'
  person=tokens&{'patient','subject','enrollee','beneficiary','client','person','individual','recipient','member','लाभार्थी','रोगी','मरीज','mareez'}
  identity=tokens&{'name','alias','identity','handle','indicator','signature','subject','नाम','पहचान','संकेत','नामांकित','pehchan','naam'}
  if person and identity:return 'name'
  if tokens & CLINICAL_MEASURE:return None
  return None
def _labeled_values(document):
  if document.fmt in ('.csv','.tsv'):
    for row in document.data:
      for key,value in zip(document.header,row):
        role=_independent_label_role(key)
        if role and isinstance(value,str):yield role,value
    return
  if document.fmt=='.txt':
    for match in re.finditer(r'(?im)^[ \t]*(?P<label>[^:=\r\n]{1,64})[ \t]*[:=][ \t]*(?P<value>[^\r\n,;|]+)',document.data):
      role=_independent_label_role(match['label'])
      if role:yield role,match['value'].strip()
    return
  def walk(value,parents=(),resource=''):
    if isinstance(value,dict):
      resource=value.get('resourceType',resource)
      for key,child in value.items():
        role=_independent_label_role(key,parents,resource)
        if role and isinstance(child,str):yield role,child
        if isinstance(child,(dict,list)):yield from walk(child,parents+(key,),resource)
    elif isinstance(value,list):
      for child in value:yield from walk(child,parents,resource)
  yield from walk(document.data)

def expand(t):
  t=unescape(unquote(t));parts=[t]
  for m in B64.finditer(t):
    try:
      s=base64.b64decode(m[0]+'='*(-len(m[0])%4),validate=True).decode('utf-8')
      if s.isprintable():parts.append(s)
    except (ValueError,UnicodeError):pass
  return '\n'.join(parts)
def probes(v,key='',inclinical=False):
  if isinstance(v,dict):
    for k,x in v.items():yield from probes(x,label(k),inclinical or label(k) in CLINICAL)
  elif isinstance(v,list):
    for x in v:yield from probes(x,key,inclinical)
  elif isinstance(v,(int,float,str)) and not isinstance(v,bool) and inclinical and key not in {'reference','id','system'}:yield str(v)

def located(data,loc):
  if loc=='doc':return data
  if loc.startswith('row:'):return data[int(loc[4:])+1]
  if not loc.startswith('/'):raise ValueError('invalid_locator')
  for part in loc[1:].split('/'):
    part=part.replace('~1','/').replace('~0','~');data=data[int(part)] if isinstance(data,list) else data[part]
  return data

def compare_clinical(original,transformed,findings,checks,active=False,key=''):
  """Compare clinical leaves at original paths, not elsewhere in a file."""
  if isinstance(original,dict):
    for k,v in original.items():
      lk=label(k)
      if lk in {'id','reference','system'}:continue
      if not isinstance(transformed,dict) or k not in transformed:
        if active or lk in CLINICAL:findings['clinical_probe_missing']+=1
        continue
      compare_clinical(v,transformed[k],findings,checks,active or lk in CLINICAL,lk)
  elif isinstance(original,list):
    if not isinstance(transformed,list):
      if active:findings['clinical_probe_missing']+=1
      return
    if active and len(original)!=len(transformed):findings['clinical_probe_missing']+=1
    for a,b in zip(original,transformed):compare_clinical(a,b,findings,checks,active,key)
  elif active and isinstance(original,(str,int,float)) and not isinstance(original,bool):
    checks['clinical_path_checks']+=1
    if type(original)!=type(transformed) or original!=transformed:findings['clinical_path_changed']+=1

def bundle_errors(v):
  if not isinstance(v,dict) or v.get('resourceType')!='Bundle':return 0
  err=0;targets=set();refs=[]
  for e in v.get('entry',[]):
    if not isinstance(e,dict) or not isinstance(e.get('resource'),dict):err+=1;continue
    r=e['resource'];rid=r.get('id');typ=r.get('resourceType');url=e.get('fullUrl')
    if not isinstance(typ,str) or not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9\-.]{1,64}',rid):err+=1
    else:targets.add(typ+'/'+rid)
    if url:
      if url in targets:err+=1
      targets.add(url)
  def scan(x):
    if isinstance(x,dict):
      for k,y in x.items():
        if k=='reference' and isinstance(y,str):refs.append(y)
        else:scan(y)
    elif isinstance(x,list):
      for y in x:scan(y)
  scan(v)
  err+=sum(ref not in targets and not ref.startswith('#') for ref in refs)
  if v.get('type')=='document' and (not v.get('entry') or v['entry'][0].get('resource',{}).get('resourceType')!='Composition'):err+=1
  return err

def verify(entries, artifacts, documents):
  findings=Counter();checks=Counter()
  detailed_findings=[]
  try:
    report=json.loads(artifacts['report.json']);rows=[json.loads(x) for x in artifacts['records.jsonl'].splitlines()]
    expected=Counter(hashlib.sha256(b).hexdigest() for _,b in entries)
    if expected!=Counter(x['input_sha256'] for x in report['files']):
      findings['accounting']+=1
      detailed_findings.append(DetailedFinding(
        file_ref='report.json', record_locator='doc',
        category='accounting', reason='Input file hash mismatch in release report',
        suggested_action='Verify input files match the processed dataset'
      ))
    declared={x['output'] for x in report['files'] if x['status']=='sanitized'};actual={k for k in artifacts if k.startswith('sanitized/')}
    if actual!=declared:
      findings['accounting']+=1
      detailed_findings.append(DetailedFinding(
        file_ref='report.json', record_locator='doc',
        category='accounting', reason='Sanitized output set does not match declared outputs',
        suggested_action='Re-run pipeline to ensure all sanitized files are produced'
      ))
    if len(rows)!=report['counts']['records_processed']:
      findings['accounting']+=1
      detailed_findings.append(DetailedFinding(
        file_ref='records.jsonl', record_locator='doc',
        category='accounting', reason='Record count mismatch between report and records log',
        suggested_action='Check for record processing errors'
      ))
    docs_by_path={d.output:d for d in documents};seen=set();cache={}
    for r in rows:
      checks['record_references']+=1
      if r['file'] not in actual:
        findings['missing_record_file']+=1
        detailed_findings.append(DetailedFinding(
          file_ref=r['file'], record_locator=r.get('loc','unknown'),
          category='missing_record_file', reason='Record references a sanitized file that was not produced',
          suggested_action='Re-run pipeline to generate missing sanitized output'
        ));continue
      key=(r['file'],r.get('loc'))
      if key in seen:
        findings['accounting']+=1
        detailed_findings.append(DetailedFinding(
          file_ref=r['file'], record_locator=r.get('loc','unknown'),
          category='accounting', reason='Duplicate record reference in output log',
          suggested_action='Check for duplicate record emission in pipeline'
        ))
      seen.add(key)
      d=docs_by_path.get(r['file'])
      if d is None:
        findings['accounting']+=1
        detailed_findings.append(DetailedFinding(
          file_ref=r['file'], record_locator=r.get('loc','unknown'),
          category='accounting', reason='Referenced sanitized file not found in document index',
          suggested_action='Verify pipeline output completeness'
        ));continue
      try:
        if r['file'] not in cache:
          t=artifacts[r['file']].decode('utf-8');cache[r['file']]=json.loads(t) if d.fmt=='.json' else list(csv.reader(io.StringIO(t),delimiter=d.delimiter)) if d.fmt in ('.csv','.tsv') else t
        unit=located(cache[r['file']],r['loc'])
        if r.get('patient') and r['patient'] not in json.dumps(unit,ensure_ascii=False):
          findings['missing_pseudonym']+=1
          detailed_findings.append(DetailedFinding(
            file_ref=r['file'], record_locator=r.get('loc','unknown'),
            category='missing_pseudonym', reason='Pseudonymous patient ID not found in record at declared locator',
            suggested_action='Verify pseudonym mapping consistency in transformation step'
          ))
      except (IndexError,KeyError,ValueError,TypeError):
        findings['invalid_record_locator']+=1
        detailed_findings.append(DetailedFinding(
          file_ref=r['file'], record_locator=r.get('loc','unknown'),
          category='invalid_record_locator', reason='Record locator does not resolve in sanitized output',
          suggested_action='Check record locator format and pipeline emission logic'
        ))
    for d in documents:
      if d.output not in actual:continue
      checks['files']+=1;t=artifacts[d.output].decode('utf-8');hay=fold(expand(t))
      for r in d.records:
        e=r.evidence
        for val in sorted(e.phones|e.strong|e.ids):
          if len(val)>=6:
            checks['known_identifiers']+=1
            if val.casefold() in re.sub(r'[- /]','',hay):
              findings['known_identifier']+=1
              detailed_findings.append(DetailedFinding(
                file_ref=d.output, record_locator='doc',
                category='known_identifier', reason='Known direct identifier detected in sanitized output',
                suggested_action='Review transformation rules for identifier replacement'
              ))
        for name in sorted(e.names|e.relatives):
          if len(name.split())<2:continue
          checks['known_names']+=1
          cleaned=re.sub(r'(?i)\bdr\.?\s+'+re.escape(fold(name)), '',hay)
          if fold(name) in cleaned:
            findings['known_name']+=1
            detailed_findings.append(DetailedFinding(
              file_ref=d.output, record_locator='doc',
              category='known_name', reason='Known name or relative name detected in sanitized output',
              suggested_action='Review name generalization and replacement logic'
            ))
      compact_hay=re.sub(r'[^a-z0-9\u0900-\u097f]','',hay)
      for role,value in _labeled_values(d):
        checks['independent_labeled_values']+=1
        candidate=fold(value).split(';',1)[0].split(',',1)[0].strip()
        if role in {'name','relative'}:
          candidate=re.split(r'(?i)\s+(?:age|aged|years?|yrs?|dob|mrn|uhid|diagnosis|medicine|आयु|उम्र|नामांकित)\b',candidate,maxsplit=1)[0].strip(' .:-')
          if len(candidate.split())<2:continue
          if candidate in hay:
            findings['residual_labeled_pii']+=1
            detailed_findings.append(DetailedFinding(
              file_ref=d.output, record_locator='doc',
              category='residual_labeled_pii', reason=f'Residual labeled PII ({role}) detected in sanitized output',
              suggested_action=f'Review {role} field transformation and generalization'
            ))
        else:
          compact=re.sub(r'[^a-z0-9\u0900-\u097f]','',candidate)
          if candidate and (candidate in hay or (len(compact)>=7 and compact in compact_hay)):
            findings['residual_labeled_pii']+=1
            detailed_findings.append(DetailedFinding(
              file_ref=d.output, record_locator='doc',
              category='residual_labeled_pii', reason=f'Residual labeled PII ({role}) detected in sanitized output',
              suggested_action=f'Review {role} field transformation and generalization'
            ))
      if d.fmt=='.json':
        v=json.loads(t);findings['fhir_reference_or_structure']+=bundle_errors(v)
        if bundle_errors(v)>0:
          detailed_findings.append(DetailedFinding(
            file_ref=d.output, record_locator='doc',
            category='fhir_reference_or_structure', reason='FHIR Bundle reference or structure errors detected',
            suggested_action='Validate FHIR Bundle structure and reference integrity'
          ))
        compare_clinical(d.data,v,findings,checks)
        for p in probes(d.data):
          checks['clinical_probes']+=1
          if fold(p) not in hay:
            findings['clinical_probe_missing']+=1
            detailed_findings.append(DetailedFinding(
              file_ref=d.output, record_locator='doc',
              category='clinical_probe_missing', reason='Clinical value not preserved in sanitized output',
              suggested_action='Verify clinical value preservation in transformation'
            ))
      elif d.fmt in ('.csv','.tsv'):
        parsed=list(csv.reader(io.StringIO(t),delimiter=d.delimiter,strict=True))
        if len(parsed)!=len(d.data)+1 or any(len(x)!=len(d.header) for x in parsed):
          findings['table_shape']+=1
          detailed_findings.append(DetailedFinding(
            file_ref=d.output, record_locator='doc',
            category='table_shape', reason='Table shape mismatch between original and sanitized output',
            suggested_action='Check row/column preservation in CSV/TSV transformation'
          ))
        for i,orig in enumerate(d.data):
          if i+1>=len(parsed):break
          for j,k in enumerate(d.header):
            if label(k) in CLINICAL:
              checks['clinical_probes']+=1
              if j>=len(parsed[i+1]) or orig[j]!=parsed[i+1][j]:
                findings['clinical_probe_missing']+=1
                detailed_findings.append(DetailedFinding(
                  file_ref=d.output, record_locator=f'row:{i}',
                  category='clinical_probe_missing', reason=f'Clinical field "{k}" not preserved in sanitized output',
                  suggested_action='Verify clinical column preservation in tabular transformation'
                ))
      plain=expand(t+'\n'+d.output)
      plain=re.sub(r'(?i)\b(?:PSN|R|KEY|doc|dir)-[0-9a-f]{20}\b|\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b','',plain)
      if DIRECT.search(plain):
        findings['residual_direct_pattern']+=1
        detailed_findings.append(DetailedFinding(
          file_ref=d.output, record_locator='doc',
          category='residual_direct_pattern', reason='Residual direct identifier pattern (phone, email, PAN, card) detected in sanitized output',
          suggested_action='Review direct identifier detection and replacement rules'
        ))
  except (ValueError,KeyError,TypeError,UnicodeError,IndexError,AttributeError):
    findings['verification_error']+=1
    detailed_findings.append(DetailedFinding(
      file_ref='unknown', record_locator='unknown',
      category='verification_error', reason='Verification encountered an unexpected error',
      suggested_action='Check pipeline output format and re-run verification'
    ))
  findings={k:v for k,v in sorted(findings.items()) if v}
  structural=not any(k in findings for k in ('accounting','missing_record_file','missing_pseudonym','table_shape','fhir_reference_or_structure','invalid_record_locator','verification_error'))
  return {'approved':structural and not findings,'contractValid':structural,'checks':dict(checks),'findings':findings,'scope':'internal conservative checks; not proof of anonymity or full FHIR R4 conformance','detailed_findings':detailed_findings}
