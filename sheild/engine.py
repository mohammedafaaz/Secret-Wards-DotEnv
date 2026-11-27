"""Offline, memory-resident privacy pipeline. No evaluation truth is used at runtime."""
from __future__ import annotations
import base64, csv, datetime as dt, hashlib, hmac, html, io, json, os, re, stat, time, unicodedata, uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from functools import lru_cache
from urllib.parse import unquote, urlsplit
from models.v2.model_features import name_key, canonical, comparison, eligible
try:
 from rapidfuzz.fuzz import ratio
except ImportError:
 from difflib import SequenceMatcher
 def ratio(a,b): return SequenceMatcher(None,a,b).ratio()*100

MAX_FILE=16*1024*1024; MAX_TOTAL=256*1024*1024; MAX_FILES=30000; MAX_DIRECTORIES=30000; MAX_DIRECTORY_ENTRIES=60000
FHIR_PATIENT_SCOPED={'Account','AllergyIntolerance','Appointment','CarePlan','CareTeam','Claim','ClinicalImpression','Composition','Condition','Coverage','DeviceRequest','DeviceUseStatement','DiagnosticReport','DocumentReference','Encounter','EpisodeOfCare','FamilyMemberHistory','Goal','ImagingStudy','Immunization','MedicationAdministration','MedicationRequest','MedicationStatement','NutritionOrder','Observation','Procedure','QuestionnaireResponse','RelatedPerson','RiskAssessment','ServiceRequest','Specimen','Task'}
FHIR_OWNER_KEYS={'subject','patient','individual','beneficiary','person','subscriber'}
FHIR_CONTEXT_KEYS={'basedOn','context','derivedFrom','encounter','episodeOfCare','partOf'}
FHIR_BUNDLE_TYPES={'document','message','transaction','transaction-response','batch','batch-response','history','searchset','collection'}
FHIR_REQUIRED_FIELDS={'Encounter':('status','class'),'Observation':('status','code'),'Condition':('code',),'DiagnosticReport':('status','code'),'Procedure':('status',),'Composition':('status','type','date','author','title'),'RelatedPerson':('patient',)}
SAFE_QUARANTINE_REASONS={'binary_content','depth_limit','duplicate_header','duplicate_json_key','duplicate_path','empty_file','empty_table','file_limit','fhir_ambiguous_ownership','fhir_duplicate_full_url','fhir_duplicate_resource','fhir_invalid_bundle','fhir_invalid_entry','fhir_ownership_missing','fhir_ownership_unresolved','invalid_encoding','invalid_encoding_marker','invalid_table_shape','multi_patient_bundle_unsupported','nonfinite_json','unsafe_path','unsupported_format'}
ZERO=re.compile('[\u200b-\u200f\u202a-\u202e\u2060\ufeff]')
DATE=re.compile(r'(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4})(?!\d)')
# Matches Indian mobile: optional +91/0 prefix then 10 digits starting [6-9], OR bare 11-digit
# numbers starting [6-9] (e.g. 81234567890 where leading digit is part of the number).
PHONE=re.compile(r'(?<!\d)(?:(?:\+?91[ -]?)?0?[6-9]\d{4}[ -]?\d{5}|[6-9]\d{10})(?!\d)')
ID=re.compile(r'(?i)(?<![\w])(?:[A-Z]{2,12}[-/]?(?:\d{2,4}[-/])?\d{3,12}|[A-Z]{2,12}\d{4}[-/]\d{3,12})(?![\w])')
PATTERNS=[('EMAIL',re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|[\w.-]+@abdm\b',re.I)),('PAN',re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b',re.I)),('ABHA',re.compile(r'(?<!\d)\d{2}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}(?!\d)')),('AADHAAR',re.compile(r'(?<!\d)(?:\d{4}[ -]?\d{4}[ -]?\d{4}|[Xx*]{4}[ -]?[Xx*]{4}[ -]?\d{4})(?!\d)')),('PHONE',PHONE),('ID',ID)]
# Keep clinical structures distinct from identity-bearing fields; arbitrary labels are normalized.
def nk(s): return re.sub(r'[^a-z0-9\u0900-\u097f]+','',unicodedata.normalize('NFKC',str(s)).casefold())
def norm(s): return ' '.join(ZERO.sub('',unicodedata.normalize('NFKC',str(s))).casefold().split())
def idkey(s): return re.sub(r'[^a-z0-9]','',norm(s))
def namekey(s): return name_key(str(s))
NAME={'patientname','patient','name','naam','nam','रोगी','मरीज','नाम','beneficiary','beneficiaryname','rogivivaran','fullname','firstname','lastname','first','last','local','given','family','familyname','patientfullname','पेशेंट',
      # Unfamiliar alias/subject keys that carry patient identity; compound forms only to avoid
      # misclassifying bare demographic or FHIR structural fields.
      'subjectalias','subjectname','enrolleealias','enrolleename','clientalias','लाभार्थीसंकेत','लाभार्थी'}
REL={'relativename','relative','guardian','guardianname','father','fathername','mother','mothername','husband','husbandname','wife','wifename','spouse','partner','sister','brother','daughter','son','child','contactperson','contactname','nextofkin','caregiver','pitapatikanaam','emergencycontactperson','attendant','raisedby','अभिभावक','पिता','माता','पति','पत्नी','परिजन','पुत्र','पुत्री','भाई','बहन','बेटा','बेटी','पापा','मम्मी','रिश्तेदार','साथी',
    # Unfamiliar kin/witness compound keys; bare 'kin', 'witness', 'familyname', 'familymember'
    # are intentionally excluded: 'familyname' conflicts with FHIR patient surname field,
    # 'kin'/'witness' alone are too broad, 'familymember' matches FamilyMemberHistory resource.
    'kinsignature','kinname','familywitness','witnessname','accompanyingperson','साथआयाव्यक्ति','साथआया','परिवारसाक्षी'}
LOCAL={'uhid','mrn','patientid','patientref','personid','personref','hospitaluhid','regno','registrationno','facilitypersonreference','chartnumber','medicalrecordnumber','patientnumber','hospitalid','regnumber'}
STRONG={'aadhaar','aadhar','aadhaarno','aadharno','aadhaarnumber','abha','abhano','abhanumber','आधार','आभा'}
CONTACT={'phone','mobile','mobileno','mobilenumber','phonenumber','contactnumber','callback','email','emailaddress','abhaaddress','samparksutra','मोबाइल','फोन','संपर्क',
        # Unfamiliar contact/reach compound keys only; bare 'contact' is already covered above.
        'contactkey','reachkey','callbackkey','contactdetail','reachnumber','संपर्कसूत्र'}
DOB={'dob','dobmmddyyyy','birthdate','dateofbirth','janmtithi','janmdinank','जन्मतिथि','जन्मदिनांक'}
AGE={'age','umar','आयु','उम्र','completedyears','agesex'}
LOC={'pata','address','homeaddress','residentialaddress','registeredaddress','street','streetaddress','addressnote','line','village','villagemohalla','gaon','ग्राम','गांव','पता','niwassthan','residence','residencesthal','ghar','घर','निवास','निवासस्थल','house','houseno','locality','landmark','postalcode','pincode','pin','zip','city','mohalla','tehsil'}
OTHERID={'visitid','billno','pmjayid','payerpan','policyno','insuranceid','pan','sampleid','registrationid','encounterid','ipdno','opdno','policy','insurance','maskedaadhaar'}
CLIN={'drug','medicine','medication','strength','dose','dosage','frequency','duration','test','loinc','unit','range','refrange','referencerange','result','bp','pulse','tempf','spo2','weightkg','diagnosis','procedure','code','display','doctor','refdoctor','referredby','consultant','physician','practitioner','amountinr','department','ward','status','form','category','schedule','gender','sex','ling','beds','occupied','denguecases','valuequantity','system','resourcetype','intent','class','qualification','country','state','district','jila','hospital','lab'}
DATEKEY={'date','visitdate','admissiondate','dischargedate','registeredon','registeredmmddyyyy','regdate','registrationdate','collected','collectedon','reportedon','effectivedatetime','authoredon','recordeddate','performeddatetime','start','end','timestamp','lastupdated','generatedat','generated','exportedat'}
META={'sourcepath','filename','filepath','source','exportedby','createdby','updatedby'}
MEDWORDS=re.compile(r'(?i)\b(?:fever|cough|pain|headache|weakness|diabetes|dengue|infection|disease|syndrome|disorder|hypertension|vomiting|nausea|breathlessness|giddiness|chest|abdomen|asthma|malaria|typhoid|mg|mcg|mmhg|ml|dose|tablet|paracetamol|metformin|insulin|bp|pulse|spo2|rbs|hba1c|history|patient|admitted|medicine|review|stable|complaints|days|weeks|months|years)\b|बुखार|खांसी|दर्द|दवा|रोग')
WORD=r'[A-Za-z\u0900-\u097f][A-Za-z\u0900-\u097f.\'’-]*'
NAMESEQ=WORD+r'(?:[ \t]+'+WORD+r'){0,3}'
RELATIVE_ROLE=re.compile(r'(?i)\b(?:guardian|father|mother|husband|wife|spouse|partner|sister|brother|daughter|son|child|relative|attendant|witness|raised\s+by|contact(?:\s+(?:person|name))?|caregiver|next\s+of\s+kin|papa|mummy|pita|mata|pati|patni|behen|bhai|beti|beta|kin(?:\s+signature)?|family\s+(?:witness|member)|accompanying\s+person)\b|अभिभावक|पिता|माता|पति|पत्नी|परिजन|पुत्र|पुत्री|भाई|बहन|बेटा|बेटी|पापा|मम्मी|रिश्तेदार|साथी|साथ\s+आया\s+व्यक्ति|परिवार\s+साक्षी')
LABEL=re.compile(r'(?im)(?:\b(?:patient\s*(?:name)?|name|beneficiary|client(?:\s+name)?|subject(?:\s+(?:name|alias))?|enrollee(?:\s+(?:name|alias))?|registration(?:\s+name)?|naam|pt\.?|guardian(?:\s+name)?|father(?:\s+name)?|mother(?:\s+name)?|husband(?:\s+name)?|wife(?:\s+name)?|spouse|partner|sister|brother|daughter|son|child|attendant|relative(?:\s+name)?|witness(?:ed\s+by)?|raised\s+by|contact(?:\s+(?:person|name))?|caregiver|next\s+of\s+kin|papa|mummy|kin(?:\s+signature)?|family\s+(?:witness|member)|accompanying\s+person)\b|नाम|मरी[ज़ज]़?(?:[ \t]+का[ \t]+नाम)?|रोगी|पंजीकरण|रजिस्ट्रेशन|लाभार्थी(?:[ \t]+संकेत)?|पिता(?:[ \t]+का[ \t]+नाम)?|माता(?:[ \t]+का[ \t]+नाम)?|पति(?:[ \t]+का[ \t]+नाम)?|पत्नी|पुत्र|पुत्री|भाई|बहन|बेटा|बेटी|पापा|मम्मी|अभिभावक|परिजन|रिश्तेदार|साथी|साथ[ \t]+आया[ \t]+व्यक्ति|परिवार[ \t]+साक्षी)\s*[:=]\s*([^\n,;|]+)')
LABELED_FIELD=re.compile(r'(?im)^[ \t]*(?P<label>[^:=\r\n]{1,64})[ \t]*[:=][ \t]*(?P<value>[^\r\n,;|]+)')
KIN=re.compile(r'(?i)(?<![\w/])(?:[sdw]/o|son of|daughter of|wife of|husband of|care of|c/o|father(?:\s+name)?|mother(?:\s+name)?|husband|wife|spouse|partner|sister|brother|daughter|son|child|papa|mummy|pita ka naam|pati ka naam|kin(?:\s+signature)?|family\s+(?:witness|member)|accompanying\s+person|पिता(?:[ \t]+का[ \t]+नाम)?|माता(?:[ \t]+का[ \t]+नाम)?|पति|पत्नी|पुत्र|पुत्री|भाई|बहन|बेटा|बेटी|पापा|मम्मी|अभिभावक|परिजन|रिश्तेदार|साथी|साथ[ \t]+आया[ \t]+व्यक्ति|परिवार[ \t]+साक्षी)\s*[:=]?\s*('+NAMESEQ+r')')
HON=re.compile(r'(?i)('+WORD+r'(?:[ \t]+'+WORD+r')?)[ \t]+(?:ji|sahab|didi|amma|bhaiya|bhai|behenji|babu|chachu|mama|papa|जी|साहब)\b')
DOCTOR=re.compile(r'(?i)\b(?:Dr\.?|Doctor)\s+'+WORD+r'(?:[ \t]+[A-Z][A-Za-z.\'’-]*){0,2}')
ADDRESS=re.compile(r'(?im)(?:\b(?:(?:home|residential|registered|street|house)[ \t]+)?(?:address|pata|village|gaon|residence|pin(?:[ \t]*code)?|ghar)(?:[ \t]*\([^\r\n)]{1,48}\))?[ \t]*[:=]|(?:पता|ग्राम|गांव|पिन|निवास(?:[ \t]+स्थल)?|घर(?:[ \t]+का[ \t]+पता)?)[ \t]*[:=])[ \t]*[^\r\n;]+?(?=(?:[.;।][ \t]+(?=(?:bp|hba1c|pulse|temp(?:erature)?|spo2|glucose|sugar|rbs|medicine|metformin|aspirin|insulin|paracetamol|medication|drug|dose|tablet|diagnosis|procedure|fever|cough|pain|बीपी|रक्तचाप|नाड़ी|तापमान|ग्लूकोज़|मेटफॉर्मिन|दवा|गोली|बुखार|खांसी|दर्द)(?=[ \t;,.।]|$))|[;\r\n]|$))')
LOCATION_WORD=r"[A-Za-z\u0900-\u0963\u0966-\u097f][A-Za-z\u0900-\u0963\u0966-\u097f'’-]*"
LOCATION_MENTION=re.compile(r'(?im)(?:\b(?:lives|resides|stays)\s+at|\b(?:home|residence|address)\s+(?:is|[:=])|\b(?:entered|came|arrived)\s+from|(?:घर(?:[ \t]+का[ \t]+पता)?|निवास(?:[ \t]+स्थल)?|घर|ghar)(?:[ \t]+(?:is|है))?[ \t]*[:=]?)\s*(?P<value>'+LOCATION_WORD+r'(?:[ \t]+'+LOCATION_WORD+r'){0,4})')
PATIENT_MENTION=re.compile(r'(?im)(?:\bpatient(?![ \t]+name\b)|मरीज|रोगी)[ \t]+(?P<value>'+NAMESEQ+r')')
AGE_TEXT=re.compile(r'(?i)(?<!\d)(\d{1,3})(?=\s*(?:yrs?\b|years?\b|y\s*/|साल|वर्ष|saal|/\s*[MF]\b))')
DOB_TEXT=re.compile(r'(?im)(?:\b(?:DOB|date of birth|birth date)\b|जन्म तिथि)\s*[:=]\s*('+DATE.pattern+r')')
B64=re.compile(r'^[A-Za-z0-9+/\s]{24,}={0,2}$')

def _field_tokens(key):
 value=unicodedata.normalize('NFKC',str(key))
 value=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',value)
 return {nk(part) for part in re.findall(r'[A-Za-z0-9]+|[\u0900-\u097f]+',value) if nk(part)}

def _semantic_field_role(key):
 tokens=_field_tokens(key)
 if tokens&{'clinician','doctor','practitioner','physician','consultant'}:return 'clinical'
 if tokens&{'email','emailaddress','e-mail'}:return 'direct'
 if tokens&{'contact','reach','callback','phone','mobile','telephone','tel','sampark','संपर्क','मोबाइल','फोन','दूरभाष'}:return 'phone'
 if tokens&{'kin','guardian','relative','attendant','caregiver','father','mother','husband','wife','spouse','sister','brother','daughter','son','parent','परिजन','रिश्तेदार','अभिभावक','पिता','माता','पति','पत्नी','पुत्र','पुत्री','भाई','बहन','साक्षी','rishtedaar','sambandhi'}:return 'relative'
 if tokens&{'family','household','परिवार','parivar'} and tokens&{'witness','सदस्य','relative','signature','person','contact','साक्षी','व्यक्ति','संबंधी','परिजन','sakshi'}:return 'relative'
 if ('accompanying' in tokens and 'person' in tokens) or ('साथ' in tokens and tokens&{'व्यक्ति','परिजन','संबंधी','रिश्तेदार'}) or ('saath' in tokens and tokens&{'vyakti','rishtedaar','sambandhi'}):return 'relative'
 person=tokens&{'patient','subject','enrollee','beneficiary','client','person','individual','recipient','member','लाभार्थी','रोगी','मरीज','mareez'}
 identity=tokens&{'name','alias','identity','handle','indicator','signature','नाम','पहचान','संकेत','नामांकित','pehchan','naam'}
 if person and identity:return 'name'
 if tokens&{'patient','subject','beneficiary','लाभार्थी','रोगी','मरीज'}:return 'name'
 return None

def field_role(key, parents=(), resource=''):
 k=nk(key); p={nk(x) for x in parents}
 if resource in ('Practitioner','Organization') and k in NAME|CONTACT: return 'clinical'
 semantic=_semantic_field_role(key)
 if semantic:return semantic
 if k in REL or (k in NAME and p&{'guardian','relative','contact','raisedby','attendant'}):return 'relative'
 if k=='name' and p&{'facility','hospital','panels','panel','lab','organization','serviceprovider'}:return 'clinical'
 if k in NAME:return 'name'
 if k in LOCAL:return 'local_id'
 if k in STRONG:return 'strong_id'
 if k in CONTACT:return 'phone' if 'email' not in k and 'abhaaddress'!=k else 'direct'
 if k in DOB:return 'dob'
 if k in AGE:return 'age'
 if k in LOC:return 'location'
 if k in OTHERID:return 'direct'
 if k in META:return 'metadata'
 if k in DATEKEY:return 'date'
 if k in CLIN:return 'clinical'
 return 'text'

def parse_date(s,monthfirst=False):
 for fmt in (['%Y-%m-%d','%m/%d/%Y','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y'] if monthfirst else ['%Y-%m-%d','%d/%m/%Y','%m/%d/%Y','%d-%m-%Y','%d.%m.%Y']):
  try:return dt.datetime.strptime(s,fmt).date(),fmt
  except ValueError:pass
 return None,None

def trim_name(s):
 s=s.strip(' \t\r\n:;,|')
 s=re.split(r'(?<!Dr\.)(?<!Mr\.)(?<!Mrs\.)(?<!Ms\.)(?<!Prof\.)(?<![A-Z]\.)(?<=[.!?।])\s+(?=[A-Za-z\u0900-\u0963\u0966-\u097f])',s,maxsplit=1)[0]
 s=re.split(r'(?i)\s{2,}|\s+(?:age|sex|aged|dob|mobile|phone|uhid|mrn|address|ka|ki|ko|ne|has|with|was|is|and|for|came|arrived|complains|presented|she|he|they|we|it|the|who|which|आयु|उम्र|को|के|का|की|ने|साथ|है|आए|आईं|आया)\b|[(:;|\d]',s)[0].strip(' .,-')
 if not s or MEDWORDS.search(s) or len(s)>100:return ''
 return s if re.fullmatch(NAMESEQ,s) else ''

@dataclass
class Evidence:
 names:set=field(default_factory=set); relatives:set=field(default_factory=set); ids:set=field(default_factory=set); strong:set=field(default_factory=set); phones:set=field(default_factory=set); dobs:set=field(default_factory=set); locations:set=field(default_factory=set); ages:set=field(default_factory=set); facilities:set=field(default_factory=set)
 def add(self,role,v,monthfirst=False):
  if v is None or isinstance(v,bool):return
  s=str(v).strip()
  if not s or s.casefold() in {'na','n/a','none','null','unknown','-'}:return
  if role in ('name','relative'):
   if len(s)<100 and not s.isnumeric(): (self.names if role=='name' else self.relatives).add(s)
  elif role=='local_id':self.ids.add(idkey(s))
  elif role=='strong_id':self.strong.add(idkey(s))
  elif role=='phone':
   p=canonical('phone',s)
   if p:self.phones.add(p)
  elif role=='dob':
   m=DATE.search(s)
   if m:
    d,_=parse_date(m.group(),monthfirst)
    if d:self.dobs.add(d.isoformat())
  elif role=='location':self.locations.add(s)
  elif role=='age':
   m=re.match(r'\d{1,3}',s)
   if m and int(m.group())<=125:self.ages.add(int(m.group()))
 def has(self):return bool(self.names or self.ids or self.strong or self.phones)

def evidence(v,ev=None,parents=(),resource='',monthfirst=False):
 ev=ev or Evidence()
 if isinstance(v,dict):
  resource=v.get('resourceType',resource)
  if resource in ('Practitioner','Organization'):return ev
  # combine split names before walking
  for a,b in [('first','last'),('FirstName','LastName'),('given','family')]:
   if a in v and b in v:
    x=v[a]; x=' '.join(x) if isinstance(x,list) and all(isinstance(y,str) for y in x) else x
    if isinstance(x,str) and isinstance(v[b],str):ev.add('name',x+' '+v[b])
  for k,x in v.items():
   if nk(k) in {'hospital','hospitalname','facility','facilityname','facilitycode','hospitalcode'} and isinstance(x,str) and x.strip():ev.facilities.add(norm(x))
   role=field_role(k,parents,resource)
   if k=='identifier' and resource=='Patient' and isinstance(x,list):
    for y in x:
     if isinstance(y,dict) and 'value' in y:ev.add('local_id',y['value'])
   elif k=='telecom' and resource=='Patient' and isinstance(x,list):
    for y in x:
     if isinstance(y,dict) and y.get('system')=='phone':ev.add('phone',y.get('value'))
   elif k=='text' and 'name' in parents and isinstance(x,str):ev.add('relative' if 'contact' in parents else 'name',x)
   elif isinstance(x,(str,int,float)) and role in ('name','relative','local_id','strong_id','phone','dob','location','age'):ev.add(role,x,monthfirst or 'mmdd' in nk(k))
   elif isinstance(x,str) and role=='text': text_evidence(x,ev,monthfirst)
   if isinstance(x,(dict,list)):evidence(x,ev,parents+(k,),resource,monthfirst)
 elif isinstance(v,list):
  for x in v:evidence(x,ev,parents,resource,monthfirst)
 elif isinstance(v,str):text_evidence(v,ev,monthfirst)
 return ev

def text_evidence(t,e,monthfirst=False):
 for m in re.finditer(r'(?im)^\s*(?:hospital|facility)(?:[ \t]+name)?[ \t]*:[ \t]*([^\r\n]+)',t):e.facilities.add(norm(m[1]))
 for m in LABELED_FIELD.finditer(t):
  role=field_role(m['label'])
  if role in ('name','relative','phone','direct','local_id','strong_id'):
   value=m['value'].strip()
   if role in ('name','relative'):value=trim_name(value)
   if value:e.add(role,value,monthfirst)
 for m in LABEL.finditer(t):
  n=trim_name(m[1]); role='relative' if RELATIVE_ROLE.search(m[0].split(':')[0].split('=')[0]) else 'name'
  if n:e.add(role,n)
 for m in PATIENT_MENTION.finditer(t):
  n=trim_name(m['value'])
  if n:e.add('name',n)
 for m in KIN.finditer(t):
  n=trim_name(m[1]);
  if n and not (m[0].lower().startswith('c/o') and re.search(r'(?i)\b(?:x|for|since)\s*\d',t[m.start():m.end()+35])):e.add('relative',n)
 for m in HON.finditer(t):
  n=trim_name(m[1]);
  if n:e.add('name',n)
 for m in ID.finditer(t):
  if re.search(r'(?i)(?:\b(?:uhid|mrn|patient\s*id|reg(?:istration)?\s*(?:no|id))\s*[:#]?\s*)$',t[max(0,m.start()-35):m.start()]):e.add('local_id',m[0])
 for m in PHONE.finditer(t):e.add('phone',m[0])
 for m in DOB_TEXT.finditer(t):e.add('dob',m[1],monthfirst)
 for m in re.finditer(r'(?im)(?:\bage(?:[ \t]*\(yrs?\))?|आयु|उम्र)[ \t]*[:=][ \t]*(\d{1,3})(?!\d|[ \t]*-)',t):e.add('age',m[1])
 for m in AGE_TEXT.finditer(t):
  if not re.search(r'(?i)(?:x|for|since|back|after|history|H/O)\s*$',t[max(0,m.start()-25):m.start()]):e.add('age',m[1])
 for m in ADDRESS.finditer(t):e.add('location',m[0].split(':',1)[-1].strip())
 for m in LOCATION_MENTION.finditer(t):e.add('location',m['value'].rstrip('.,;:।'))

@dataclass
class Record:
 loc:str; value:object; evidence:Evidence; key:str|None=None; width:int=10; generalized:bool=False; shift_key:str=''; rare:bool=False
@dataclass
class Document:
 path:str; digest:str; fmt:str; data:object; records:list; header:list=field(default_factory=list); delimiter:str=','; monthfirst:bool=False; output:str=''; fhir_ownership:dict=field(default_factory=dict)

def strict_pairs(pairs):
 d={}
 for k,v in pairs:
  if k in d:raise ValueError('duplicate_json_key')
  d[k]=v
 return d

def depth(v,d=0):
 if d>80:raise ValueError('depth_limit')
 if isinstance(v,dict):
  for x in v.values():depth(x,d+1)
 if isinstance(v,list):
  for x in v:depth(x,d+1)

def pointer(k):return str(k).replace('~','~0').replace('/','~1')
def decode(raw):
 if not raw.strip():raise ValueError('empty_file')
 if not raw.startswith((b'\xff\xfe',b'\xfe\xff')) and (b'\xff\xfe' in raw or b'\xfe\xff' in raw):raise ValueError('invalid_encoding_marker')
 if raw.startswith((b'\xff\xfe',b'\xfe\xff')):
  try:t=raw.decode('utf-16')
  except UnicodeError:raise ValueError('invalid_encoding') from None
 else:
  try:t=raw.decode('utf-8-sig')
  except UnicodeError:
   try:t=raw.decode('cp1252')
   except UnicodeError:raise ValueError('invalid_encoding') from None
 if '\ufffd' in t or any(ord(x)<32 and x not in '\t\r\n' for x in t):raise ValueError('binary_content')
 return t

def _json_value(text):
 value=json.loads(text,object_pairs_hook=strict_pairs,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite_json')))
 depth(value)
 return value

def _table_rows(text,delimiter):
 rows=list(csv.reader(io.StringIO(text,newline=''),delimiter=delimiter,strict=True))
 if not rows or not rows[0] or any(not x.strip() for x in rows[0]):raise ValueError('invalid_table_shape')
 normalized=[nk(x) for x in rows[0]]
 if len(set(normalized))!=len(normalized):raise ValueError('duplicate_header')
 if any(len(row)!=len(rows[0]) for row in rows[1:]):raise ValueError('invalid_table_shape')
 return rows

def _reference_target(reference,full_urls,resources):
 if not isinstance(reference,str) or reference.startswith('#'):return None
 if reference in full_urls:return full_urls[reference]
 candidate=unquote(reference)
 if candidate.startswith('urn:'):return None
 parts=[x for x in urlsplit(candidate).path.split('/') if x]
 if '_history' in parts:
  pos=parts.index('_history')
  if pos>=2:parts=parts[:pos]
 if len(parts)>=2:
  return resources.get(parts[-2]+'/'+parts[-1])
 return None

def _nested_references(value):
 if isinstance(value,dict):
  if isinstance(value.get('reference'),str):yield value['reference']
  else:
   for child in value.values():yield from _nested_references(child)
 elif isinstance(value,list):
  for child in value:yield from _nested_references(child)

def _scope_references(resource):
 def visit(value):
  if isinstance(value,dict):
   for key,child in value.items():
    if key in FHIR_OWNER_KEYS|FHIR_CONTEXT_KEYS:
     yield key,from_value(child)
    else:yield from visit(child)
  elif isinstance(value,list):
   for child in value:yield from visit(child)
 def from_value(value):
  yield from _nested_references(value)
 return list(visit(resource))

def _safe_input_path(path):
 if not isinstance(path,str) or not path or '\\' in path or '\x00' in path or any(ord(char)<32 for char in path):raise ValueError('unsafe_path')
 p=PurePosixPath(path)
 if p.is_absolute() or path!=p.as_posix() or any(part in ('','.','..') or ':' in part or part.endswith((' ','.')) or any(char in '<>:"|?*' for char in part) for part in p.parts):raise ValueError('unsafe_path')
 if any(part.split('.',1)[0].casefold() in {'con','prn','aux','nul'}|{f'com{i}' for i in range(1,10)}|{f'lpt{i}' for i in range(1,10)} for part in p.parts):raise ValueError('unsafe_path')
 return unicodedata.normalize('NFC',p.as_posix()).casefold()

def _fhir_records(bundle,monthfirst):
 entries=bundle.get('entry',[])
 if bundle.get('type') not in FHIR_BUNDLE_TYPES or not isinstance(entries,list):raise ValueError('fhir_invalid_bundle')
 full_urls={};resources={};types=[];patient_entries=[]
 for index,entry in enumerate(entries):
  if not isinstance(entry,dict) or not isinstance(entry.get('resource'),dict):raise ValueError('fhir_invalid_entry')
  resource=entry['resource'];resource_type=resource.get('resourceType');rid=resource.get('id');full_url=entry.get('fullUrl')
  if not isinstance(resource_type,str) or not re.fullmatch(r'[A-Z][A-Za-z0-9]{0,63}',resource_type):raise ValueError('fhir_invalid_entry')
  if any(not resource.get(key) for key in FHIR_REQUIRED_FIELDS.get(resource_type,())):raise ValueError('fhir_invalid_entry')
  if resource_type=='MedicationRequest' and (not resource.get('status') or not resource.get('intent') or not (resource.get('medicationCodeableConcept') or resource.get('medicationReference'))):raise ValueError('fhir_invalid_entry')
  if resource_type=='DocumentReference' and (not resource.get('status') or not resource.get('content')):raise ValueError('fhir_invalid_entry')
  if rid is not None:
   if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9.-]{1,64}',rid):raise ValueError('fhir_invalid_entry')
   key=resource_type+'/'+rid
   if key in resources:raise ValueError('fhir_duplicate_resource')
   resources[key]=index
  if full_url is not None:
   if not isinstance(full_url,str) or not full_url or full_url in full_urls:raise ValueError('fhir_duplicate_full_url')
   full_urls[full_url]=index
  if resource_type=='Patient':patient_entries.append(index)
  types.append(resource_type)
 records=[];patient_record={}
 for index in patient_entries:
  loc='doc' if len(patient_entries)==1 else f'/entry/{index}/resource'
  patient_record[index]=len(records)
  records.append(Record(loc,bundle['entry'][index]['resource'],evidence(bundle['entry'][index]['resource'],monthfirst=monthfirst)))
 owners=[set() for _ in entries]
 for index in patient_entries:owners[index].add(patient_record[index])
 edges=[set() for _ in entries];unresolved_owner=[False for _ in entries]
 for index,entry in enumerate(entries):
  resource=entry['resource']
  for key,refs in _scope_references(resource):
   for reference in refs:
    target=_reference_target(reference,full_urls,resources)
    if target is None:
     if key in FHIR_OWNER_KEYS:unresolved_owner[index]=True
     continue
    edges[index].add(target)
 while True:
  changed=False
  for index,targets in enumerate(edges):
   before=len(owners[index])
   for target in targets:owners[index].update(owners[target])
   changed|=len(owners[index])!=before
  if not changed:break
 ownership={}
 for index,resource_type in enumerate(types):
  if resource_type in FHIR_PATIENT_SCOPED:
   if unresolved_owner[index]:raise ValueError('fhir_ownership_unresolved')
   if len(owners[index])>1:raise ValueError('fhir_ambiguous_ownership')
   if len(owners[index])!=1:raise ValueError('fhir_ownership_missing')
   ownership[index]=next(iter(owners[index]))
  elif len(owners[index])==1:
   ownership[index]=next(iter(owners[index]))
 return records,ownership

def parse(path,raw):
 ext=PurePosixPath(path).suffix.lower(); digest=hashlib.sha256(raw).hexdigest()
 if len(raw)>MAX_FILE:raise ValueError('file_limit')
 if ext not in ('.csv','.tsv','.json','.txt'):raise ValueError('unsupported_format')
 t=decode(raw); mf=bool(re.search(r'(?i)mm/dd/yyyy',t[:500]))
 slash_dates=[(int(m[1]),int(m[2])) for m in re.finditer(r'(?<!\d)(\d{1,2})/(\d{1,2})/\d{4}(?!\d)',t)]
 if not mf and any(a<=12<b<=31 for a,b in slash_dates) and not any(b<=12<a<=31 for a,b in slash_dates):mf=True
 looks_json=t.lstrip().startswith(('{','['))
 json_candidate=ext=='.json' or (looks_json and ext in ('.csv','.tsv'))
 if ext=='.txt' and looks_json:
  try:json.loads(t)
  except json.JSONDecodeError:pass
  else:json_candidate=True
 if json_candidate:
  v=_json_value(t)
  units=[]
  if isinstance(v,dict) and v.get('resourceType')=='Bundle':
   records,ownership=_fhir_records(v,mf)
   return Document(path,digest,'.json',v,records,monthfirst=mf,fhir_ownership=ownership)
  elif isinstance(v,list) and all(isinstance(x,dict) for x in v):units=[('/'+str(i),x,evidence(x,monthfirst=mf)) for i,x in enumerate(v)]
  elif isinstance(v,dict):
   # Patient-bearing collection only; clinical arrays inside a single record remain intact.
   for k,x in v.items():
    if isinstance(x,list) and x and all(isinstance(y,dict) for y in x):
     es=[evidence(y,monthfirst=mf) for y in x]
     if any(e.has() for e in es) and not any(nk(z) in NAME|LOCAL for z in v):units.extend(('/'+pointer(k)+'/'+str(i),y,e) for i,(y,e) in enumerate(zip(x,es)))
   if not units:units=[('doc',v,evidence(v,monthfirst=mf))]
  else:units=[('doc',v,evidence(v,monthfirst=mf))]
  return Document(path,digest,'.json',v,[Record(*u) for u in units],monthfirst=mf)
 if ext in ('.csv','.tsv'):
  preferred='\t' if ext=='.tsv' else ','
  alternate=',' if preferred=='\t' else '\t'
  preferred_rows=None;preferred_error=None;alternate_rows=None
  try:preferred_rows=_table_rows(t,preferred)
  except (ValueError,csv.Error) as error:preferred_error=error
  if isinstance(preferred_error,ValueError) and str(preferred_error)!='invalid_table_shape':raise preferred_error
  try:alternate_rows=_table_rows(t,alternate)
  except (ValueError,csv.Error):pass
  if preferred_rows is not None:
   chosen=(preferred,preferred_rows)
   if len(preferred_rows[0])==1 and alternate_rows is not None and len(alternate_rows[0])>1:chosen=(alternate,alternate_rows)
  elif preferred_error is None and alternate_rows is not None and len(alternate_rows[0])>1:chosen=(alternate,alternate_rows)
  else:raise preferred_error if isinstance(preferred_error,ValueError) else ValueError('invalid_table_shape')
  delim,rows=chosen;fmt='.tsv' if delim=='\t' else '.csv';h=rows[0]
  rec=[Record(f'row:{i}',dict(zip(h,r)),evidence(dict(zip(h,r)),monthfirst=mf)) for i,r in enumerate(rows[1:])]
  return Document(path,digest,fmt,rows[1:],rec,h,delim,mf)
 if ext not in ('.txt',):raise ValueError('unsupported_format')
 return Document(path,digest,ext,t,[Record('doc',t,evidence(t,monthfirst=mf))],monthfirst=mf)

class Linker:
 def __init__(self,records,model):self.records=records;self.model=model;self.parent=list(range(len(records)));self.groups={i:{i} for i in range(len(records))}
 def find(self,i):
  while self.parent[i]!=i:i=self.parent[i]
  return i
 def compatible(self,a,b):
  if a.strong and b.strong and not a.strong&b.strong:return False
  if a.dobs and b.dobs and not a.dobs&b.dobs:return False
  if a.phones and b.phones and not a.phones&b.phones and not (a.strong&b.strong or a.ids&b.ids):return False
  return True
 def merge(self,i,j):
  a,b=self.find(i),self.find(j)
  if a==b:return
  if any(not self.compatible(self.records[x].evidence,self.records[y].evidence) for x in self.groups[a] for y in self.groups[b]):return
  a,b=min(a,b),max(a,b);self.parent[b]=a;self.groups[a]|=self.groups.pop(b)
 def run(self):
  blocks=defaultdict(list); keys=[]
  for i,r in enumerate(self.records):
   e=r.evidence; ns={namekey(n) for n in e.names if namekey(n)}; rs={namekey(n) for n in e.relatives if namekey(n)};keys.append(ns)
   for typ,vals in [('id',e.ids),('strong',e.strong),('phone',e.phones),('name',ns),('relative',rs),('dob',e.dobs)]:
    for v in sorted(vals):blocks[(typ,v)].append(i)
  edges={}
  for (typ,val),idx in sorted(blocks.items()):
   if len(idx)>400:continue
   for n,i in enumerate(idx):
    for j in idx[n+1:]:
     a,b=self.records[i].evidence,self.records[j].evidence
     if not self.compatible(a,b):continue
     sim=max((ratio(x,y) for x in keys[i] for y in keys[j]),default=0)
     rel=max((ratio(namekey(x),namekey(y)) for x in a.relatives for y in b.relatives),default=0)
     sharedid=bool(a.ids&b.ids) and not (a.facilities and b.facilities and a.facilities.isdisjoint(b.facilities)); strong=bool(a.strong&b.strong); phone=bool(a.phones&b.phones); dob=bool(a.dobs&b.dobs)
     score=100 if strong else 90 if sharedid and (sim>=65 or not keys[i] or not keys[j]) else 80 if sim>=78 and phone else 75 if sim>=85 and dob else 0
     if not score and sim>=85 and rel>=85:
      same_facility=bool(a.facilities and b.facilities and not a.facilities.isdisjoint(b.facilities))
      local_id_conflict=same_facility and bool(a.ids and b.ids) and not a.ids&b.ids
      if not local_id_conflict:score=70
     if self.model and score<70 and sim>=60 and (phone or dob or strong or sharedid):
      def features(e):return {'name':max(sorted(e.names),key=len,default=''),'relative':max(sorted(e.relatives),key=len,default=''),'phone':next(iter(sorted(e.phones)),''),'dob':next(iter(sorted(e.dobs)),''),'strong_id':next(iter(sorted(e.strong)),''),'local_id':next(iter(sorted(e.ids)),''),'village':next(iter(sorted(e.locations)),''),'hospital':next(iter(sorted(e.facilities)), '')}
      fa,fb=features(a),features(b)
      if not sharedid:fa['local_id']=fb['local_id']=''
      if self.model.pair(fa,fb)['candidate_link']:score=65
     if score:edges[i,j]=max(score,edges.get((i,j),0))
  for (i,j),s in sorted(edges.items(),key=lambda z:(-z[1],z[0])):self.merge(i,j)
  # Name-only is not sufficient; attach partial notes only with independent evidence.
  for root,members in sorted(self.groups.items()):
   if not any(self.records[i].evidence.has() for i in members):continue
   material='|'.join(sorted({v for i in members for v in (self.records[i].evidence.ids|self.records[i].evidence.strong|self.records[i].evidence.phones|self.records[i].evidence.dobs|{namekey(n) for n in self.records[i].evidence.names})}))+'|'+str(min(members))
   for i in members:
    e=self.records[i].evidence
    if len(members)>1 or e.ids or e.strong or (e.names and (e.phones or e.dobs)):self.records[i].key='cluster:'+material
  # Risk-aware widening: use distinct clusters in each demographic bin, not encounters.
  def diagnoses(v):
   out=set()
   if isinstance(v,dict):
    for k,x in v.items():
     if nk(k) in ('diagnosis','procedure'):
      if isinstance(x,str):out.add(norm(x))
      elif isinstance(x,list):
       for y in x:
        if isinstance(y,dict) and y.get('code'):out.add(norm(y['code']))
        elif isinstance(y,str):out.add(norm(y))
     else:out.update(diagnoses(x))
   elif isinstance(v,list):
    for x in v:out.update(diagnoses(x))
   return out
  profiles=defaultdict(list);conditions=defaultdict(set)
  for i,r in enumerate(self.records):
   k=r.key or f'unlinked:{i}';profiles[k].append(r)
   for d in diagnoses(r.value):conditions[d].add(k)
  age_support={w:defaultdict(set) for w in (5,10,20,40,80)}
  for key,rs in profiles.items():
   for a in set().union(*(r.evidence.ages for r in rs)):
    for w in age_support:age_support[w][a//w].add(key)
  for key,rs in profiles.items():
   ages=set().union(*(r.evidence.ages for r in rs));rare=any(len(conditions[d])<4 for r in rs for d in diagnoses(r.value))
   # Minimal age band meeting distinct-profile support; rare diagnoses get a
   # wider floor because exact clinical values must remain unchanged.
   width=next((w for w in ((40,80) if rare else (5,10,20,40,80)) if ages and all(len(age_support[w][a//w])>=5 for a in ages)),80 if ages else 20)
   for r in rs:r.width=width;r.rare=rare
  self.risk_summary={'profiles':len(profiles),'rare_condition_profiles':sum(any(r.rare for r in rs) for rs in profiles.values()),'coarse_age_profiles':sum(rs[0].width>=20 for rs in profiles.values()),'method':'distinct-profile age-band support (target five) with rare-diagnosis widening; not measured attacker success'}

class Engine:
 def __init__(self,secret,model=None):
  if not secret:raise ValueError('secret_required')
  self.secret=secret.encode() if isinstance(secret,str) else secret;self.model=model;self.entities=Counter();self.known={};self.rx=None;self.clinical_checks=[];self.risk=Counter();self.date_offsets={};self.forbidden_dates=set()
 def token(self,s,prefix='PSN'):
  return prefix+'-'+hmac.new(self.secret,(prefix+'|'+s).encode(),hashlib.sha256).hexdigest()[:20]
 def choose_offset(self,key,dates):
  # Keep a single secret-derived offset per patient, and reject offsets that
  # would export an original known DOB or cause date overflow. This prevents
  # accidental reuse of known private birth dates under another patient's key.
  raw=hmac.new(self.secret,('date|'+key).encode(),hashlib.sha256).digest();base=int.from_bytes(raw[:8],'big')%730
  for i in range(730):
   n=((base+i)%730)-365
   if not n:continue
   try:
    shifted=[d+dt.timedelta(days=n) for d in dates]
   except OverflowError:continue
   if not self.forbidden_dates.intersection(shifted):return n
  raise ValueError('no_safe_date_shift')
 def prepare_shifts(self,documents):
  dates=defaultdict(set);self.forbidden_dates=set()
  def walk(v,monthfirst=False):
   if isinstance(v,dict):
    for k,x in v.items():yield from walk(x,monthfirst or 'mmdd' in nk(k))
   elif isinstance(v,list):
    for x in v:yield from walk(x,monthfirst)
   elif isinstance(v,str):
    for m in DATE.finditer(v):
     d,_=parse_date(m[0],monthfirst)
     if d:yield d
  for doc in documents:
   for r in doc.records:
    for s in r.evidence.dobs:
     try:self.forbidden_dates.add(dt.date.fromisoformat(s))
     except ValueError:pass
    dates[r.key or r.shift_key].update(walk(r.value,doc.monthfirst))
   if doc.fhir_ownership:
    for i,j in doc.fhir_ownership.items():
     r=doc.records[j];dates[r.key or r.shift_key].update(walk(doc.data['entry'][i],doc.monthfirst))
  for key,ds in dates.items():
   if ds:
    try:self.date_offsets[key]=self.choose_offset(key,ds)
    except ValueError:self.date_offsets[key]=None
 def shift(self,s,key,monthfirst=False):
  d,f=parse_date(s,monthfirst)
  if d is None:return s
  if key not in self.date_offsets:self.date_offsets[key]=self.choose_offset(key,[d])
  n=self.date_offsets[key]
  if n is None:raise ValueError('no_safe_date_shift')
  try:return (d+dt.timedelta(days=n)).strftime(f)
  except OverflowError:raise ValueError('date_shift_overflow') from None
 def build_vocab(self,records):
  for r in records:
   e=r.evidence
   for typ,vals in [('name',e.names),('relative',e.relatives),('location',e.locations)]:
    for v in sorted(vals):
     if len(v)>=3 and len(v)<=180 and not MEDWORDS.search(v) and not re.search(r'(?i)\b(?:asha|worker|referred|hospital|clinic|ward|report|diagnostic|forwarded)\b',v): self.known.setdefault(norm(v),typ)
  if self.known:
   variants=sorted(self.known,key=lambda x:(-len(x),x)); self.rx=re.compile(r'(?<!\w)(?:'+'|'.join(re.escape(x).replace(r'\ ',r'[ _\t]+') for x in variants)+r')(?!\w)',re.I)
 def replace(self,kind):self.entities[kind]+=1;return ' [REDACTED]' if kind=='LOCATION' else '[REDACTED]'
 def age(self,v,r):
  m=re.match(r'\s*(\d{1,3})(.*)',str(v),re.S)
  if not m or int(m[1])>125:return v
  n=int(m[1]);w=r.width if r else 20;lo=n//w*w;r and setattr(r,'generalized',True);self.entities['AGE']+=1
  # JSON number cannot represent an interval. Use null and sibling band at object level.
  return f'{lo}-{min(lo+w-1,125)}'+m[2]
 def clean_text(self,t,r=None,role='text',monthfirst=False,allow_model=True):
  if not t:return t
  key=(r.key or r.shift_key) if r else 'unlinked:'+hashlib.sha256(t.encode()).hexdigest();pid=self.token(r.key) if r and r.key else '[REDACTED]'
  t=ZERO.sub('',t);t=''.join(str(unicodedata.decimal(c)) if c.isdecimal() and not c.isascii() else c for c in t)
  if role=='clinical':
   # Preserve known clinical text, but remove unmistakable direct identifiers in mixed fields.
   for k,rx in PATTERNS[:4]:
    t=rx.sub(lambda m:self.replace(k),t)
   return t
  if role in ('name','local_id'):self.entities[role.upper()]+=1;return pid
  if role in ('relative','strong_id','phone','direct','metadata'):return self.replace(role.upper())
  if role=='location':
   if r:r.generalized=True
   return self.replace('LOCATION').lstrip()
  if role=='age':return self.age(t,r)
  if role=='dob':
   self.entities['DOB']+=1
   return DATE.sub(lambda m:self.shift(m[0],key,monthfirst),t) if DATE.search(t) else '[REDACTED]'
  # Non-patient text may contain multiple dates; choose one offset for all.
  if key not in self.date_offsets and DATE.search(t):
   ds=[d for m in DATE.finditer(t) for d,_ in [parse_date(m[0],monthfirst)] if d]
   if ds:self.date_offsets[key]=self.choose_offset(key,ds)
  # preserve narrative markup; sanitize text nodes separately
  if t.startswith('<div') and '</div>' in t:
   return re.sub(r'>([^<>]+)<',lambda m:'>'+html.escape(self.clean_text(html.unescape(m[1]),r,monthfirst=monthfirst,allow_model=allow_model),quote=False)+'<',t)
  # protect clinical phrases and doctors from name matching (not identity-labeled relatives)
  spans=[];protected=[(m.start(),m.end()) for m in DOCTOR.finditer(t)]
  def add(a,b,kind,rep=None,force=False):
   if a>=b:return
   if not force and any(a<y and b>x for x,y in protected):return
   spans.append((a,b,kind,rep))
  for k,rx in PATTERNS:
   for m in rx.finditer(t):add(m.start(),m.end(),k,force=True)
  for m in LABELED_FIELD.finditer(t):
   role=field_role(m['label'])
   if role not in ('name','relative','phone','direct','local_id','strong_id'):continue
   value=m['value'].strip()
   if role in ('name','relative'):
    value=trim_name(value)
    if not value:continue
   leading=len(m['value'])-len(m['value'].lstrip())
   start=m.start('value')+leading
   end=start+len(value)
   add(start,end,'RELATIVE' if role=='relative' else 'NAME' if role=='name' else role,pid if role=='name' else None,True)
  for m in LABEL.finditer(t):
   n=trim_name(m[1]);
   if n:
    a=m.start(1)+len(m[1])-len(m[1].lstrip());add(a,a+len(n),'RELATIVE' if RELATIVE_ROLE.search(m[0].split(':')[0].split('=')[0]) else 'NAME',None if RELATIVE_ROLE.search(m[0].split(':')[0].split('=')[0]) else pid,True)
  for m in PATIENT_MENTION.finditer(t):
   n=trim_name(m['value'])
   if n:add(m.start('value'),m.start('value')+len(n),'NAME',pid,True)
  for m in KIN.finditer(t):
   n=trim_name(m[1]);
   if n and not (m[0].lower().startswith('c/o') and (re.search(r'(?i)\b(?:x|for|since)\s*\d',t[m.start():m.end()+35]) or re.search(r'(?i)\b(?:complaint|symptom|history)\s*[:=]\s*$',t[max(0,m.start()-35):m.start()]))):add(m.start(1),m.start(1)+len(n),'RELATIVE',force=True)
  for m in HON.finditer(t):
   n=trim_name(m[1]);
   if n:add(m.start(1),m.end(),'NAME',pid)
  for m in re.finditer(r'(?im)(?:called by|witnessed by|report of|(?:^|\n)\d{1,2}:\d{2}\s*-\s*)\s*('+NAMESEQ+r')',t):
   n=trim_name(m[1]);
   if n and not n.lower().startswith('dr'):add(m.start(1),m.start(1)+len(n),'NAME',pid)
  for m in re.finditer(r'(?m)\b\d{1,2}:\d{2}\s*-\s*('+NAMESEQ+r')(?=\s*[-(])',t):
   n=trim_name(m[1]);
   if n and not n.lower().startswith('dr'):add(m.start(1),m.start(1)+len(n),'NAME',pid)
  for m in re.finditer(r'(?i)(?:\bname|\bpatient|\brelative|\battendant)\s*[:=]\s*(Dr\.?\s+'+NAMESEQ+r')',t):add(m.start(1),m.end(1),'NAME',force=True)
  for m in ADDRESS.finditer(t):
   sep=re.search(r'[:=][ \t]*',m[0]);a=m.start()+sep.end() if sep else m.start();add(a,m.end(),'LOCATION',force=True)
  for m in LOCATION_MENTION.finditer(t):
   a,b=m.span('value')
   while b>a and t[b-1] in '.,;:।':b-=1
   add(a,b,'LOCATION')
  if self.rx:
   for m in self.rx.finditer(t):
    if not MEDWORDS.search(m[0]):add(m.start(),m.end(),'KNOWN_NAME_OR_LOCATION')
  # Possessive and kinship-linked mentions.
  for m in re.finditer(r'(?i)('+WORD+r')(?=,?\s*(?:[sdw]/o|son of|wife of|daughter of)|[’\']s\s+(?:attendant|relative|sample|report|mother|father))',t):
   if trim_name(m[1]):add(m.start(1),m.end(1),'NAME',pid)
  # Contextual short mentions; do not use single names as global removal rules.
  for m in re.finditer(r'(?i)('+WORD+r')\s+(?:ka|ki|ko|ne)\s+(?:BP|condition|tabiyat|bukhar|fever|pain|khana|dawa|report|health|pulse|sugar|complaint)',t):
   if trim_name(m[1]):add(m.start(1),m.end(1),'NAME',pid)
  # Local CRF candidates need a nearby identity cue; a candidate never creates a link by itself.
  if self.model and allow_model and len(t)<=12000 and re.search(r'(?i)patient|name|naam|guardian|father|mother|husband|wife|spouse|partner|sister|brother|daughter|son|child|contact|caregiver|next of kin|registration|registered|s/o|w/o|d/o|\bji\b|नाम|मरीज|पंजीकरण|रजिस्ट्रेशन|पिता|माता|पति|पत्नी|पुत्र|पुत्री|भाई|बहन|बेटा|बेटी|पापा|मम्मी|mobile|uhid|लाभार्थी|साथ आया|enrollee|subject|alias|witness|kin',t):
   try:
    for x in self.model.spans(t):
     a,b=x['start'],x['end'];label=x['label'];s=t[a:b];before=t[max(0,a-45):a]
     if not (0<=a<b<=len(t)) or any(c in s for c in '\r\n'):continue
     n=trim_name(s)
     prefix=len(s)-len(s.lstrip(' \t:;,|'));candidate_start=a+prefix
     if label in ('PATIENT','RELATIVE') and n and t[candidate_start:candidate_start+len(n)]==n:
      context=re.search(r'(?i)(patient(?:[ \t]+name)?|name|naam|client(?:[ \t]+name)?|subject(?:[ \t]+(?:name|alias))?|enrollee(?:[ \t]+(?:name|alias))?|guardian(?:[ \t]+name)?|father(?:[ \t]+name)?|mother(?:[ \t]+name)?|husband|wife|spouse|partner|sister|brother|daughter|son|child|contact(?:[ \t]+(?:person|name))?|caregiver|next[ \t]+of[ \t]+kin|attendant|relative(?:[ \t]+name)?|witness(?:ed[ \t]+by)?|raised[ \t]+by|registration|kin(?:[ \t]+signature)?|family[ \t]+(?:witness|member)|accompanying[ \t]+person|पंजीकरण|रजिस्ट्रेशन|नाम|मरीज|पिता|माता|पति|पत्नी|पुत्र|पुत्री|भाई|बहन|बेटा|बेटी|पापा|मम्मी|लाभार्थी(?:[ \t]+संकेत)?|साथ[ \t]+आया[ \t]+व्यक्ति|परिवार[ \t]+साक्षी)[ \t]*[:=]?[ \t]*$',before.split('\n')[-1])
      if context:
       relative=bool(RELATIVE_ROLE.search(context[1]))
       add(candidate_start,candidate_start+len(n),'RELATIVE' if relative else 'NAME',None if relative else pid,True)
   except (ValueError,OverflowError):pass
  for m in DATE.finditer(t):add(m.start(),m.end(),'DATE',self.shift(m[0],key,monthfirst),True)
  for m in re.finditer(r'(?im)(?:\bage(?:[ \t]*\(yrs?\))?|आयु|उम्र)[ \t]*[:=][ \t]*(\d{1,3})(?!\d|[ \t]*-)',t):
   if int(m[1])<=125:add(m.start(1),m.end(1),'AGE',self.age(m[1],r),True)
  for m in AGE_TEXT.finditer(t):
   if not re.search(r'(?i)(?:x|for|since|back|after|history|H/O)\s*$',t[max(0,m.start()-25):m.start()]) and not re.search(r'(?i)^\s*(?:yrs?|years?)\s+back',t[m.end():]):add(m.start(1),m.end(1),'AGE',self.age(m[1],r),True)
  # Resolve spans longest-first, then apply from right to left against original offsets.
  chosen=[]
  for a,b,k,rep in sorted(spans,key=lambda x:(x[0],-(x[1]-x[0]),x[2])):
   if any(a<y and b>x for x,y,_,_ in chosen):continue
   chosen.append((a,b,k,rep))
  for a,b,k,rep in sorted(chosen,reverse=True):
   self.entities[k]+=1;t=t[:a]+(rep if rep is not None else '[REDACTED]')+t[b:]
  return t
 def clean(self,v,r=None,parents=(),resource='',monthfirst=False):
  if isinstance(v,dict):
   resource=v.get('resourceType',resource);out={}
   for k,x in v.items():
    role=field_role(k,parents,resource);newk=k
    if (parents and parents[-1] in ('by_name','by_uhid')) or ID.search(k) or (self.rx and self.rx.search(k) and nk(k) not in NAME|CLIN|LOCAL|REL):newk=self.token(k,'KEY')
    if newk in out:raise ValueError('key_collision')
    if isinstance(x,(dict,list)):
     # FHIR identifier and name structure retained. Children handled with parent context.
     out[newk]=self.clean(x,r,parents+(k,),resource,monthfirst);continue
    if x is None or isinstance(x,bool):out[newk]=x;continue
    if k=='value' and 'identifier' in parents:role='local_id' if resource=='Patient' else 'direct'
    if k=='value' and 'telecom' in parents:role='direct'
    if k in ('text','given','family') and 'name' in parents and resource!='Practitioner':role='relative' if 'contact' in parents else 'name'
    if k=='display' and 'subject' in parents:role='name'
    if k=='valueString' and resource=='Patient':role='relative'
    if k in ('id','fullUrl','reference') and resource:
     out[newk]=x;continue # bundle graph remapped separately
    if k=='data' and isinstance(x,str) and ('attachment' in parents or B64.fullmatch(x)):
     try:
      raw=base64.b64decode(x,validate=True);decoded=raw.decode('utf-8');clean=self.clean_text(decoded,r,monthfirst=monthfirst);out[newk]=base64.b64encode(clean.encode()).decode();continue
     except (ValueError,UnicodeError):out[newk]='';self.entities['ATTACHMENT']+=1;continue
    if isinstance(x,(int,float)):
     if role=='age':out[newk]=None;out[newk+'_band']=self.age(x,r)
     elif role in ('strong_id','local_id','phone','direct','location','name','relative','dob'):out[newk]=None;self.entities[role.upper()]+=1
     else:out[newk]=x
    elif isinstance(x,str):out[newk]=self.clean_text(x,r,role,monthfirst or 'mmdd' in nk(k))
    else:out[newk]=x
   return out
  if isinstance(v,list):return [self.clean(x,r,parents,resource,monthfirst) for x in v]
  if isinstance(v,str):
   role=field_role(parents[-1],parents[:-1],resource) if parents else 'text'
   if 'name' in parents and resource=='Patient':role='relative' if 'contact' in parents else 'name'
   return self.clean_text(v,r,role,monthfirst)
  return v
 def fhir(self,v,records,ownership,monthfirst=False):
  entries=v.get('entry',[]);resources={};full_urls={};id_map={};full_url_map={}
  for index,entry in enumerate(entries):
   resource=entry['resource'];resource_type=resource.get('resourceType');rid=resource.get('id');full_url=entry.get('fullUrl')
   if isinstance(rid,str):
    resources[resource_type+'/'+rid]=index
    id_map[resource_type+'/'+rid]=self.token(resource_type+'|'+rid,'R')
   if isinstance(full_url,str):
    full_urls[full_url]=index
    full_url_map[full_url]='urn:uuid:'+str(uuid.UUID(hmac.new(self.secret,('fullurl|'+full_url).encode(),hashlib.sha256).hexdigest()[:32]))
  if isinstance(v.get('id'),str):id_map['Bundle/'+v['id']]=self.token('Bundle|'+v['id'],'R')

  def contained_ids(resource):
   mapping={}
   def collect(parent,scope):
    for child in parent.get('contained',[]) if isinstance(parent,dict) else []:
     if not isinstance(child,dict):continue
     old=child.get('id');identity=scope+'|'+str(child.get('resourceType','Resource'))+'|'+str(old or '')
     if isinstance(old,str):mapping['#'+old]='#'+self.token(identity,'R')
     collect(child,identity)
   collect(resource,str(resource.get('resourceType','Resource'))+'|'+str(resource.get('id','')))
   return mapping

  def remap(value,local_ids=None,contained=False):
   local_ids=local_ids or {}
   if isinstance(value,dict):
    resource_type=value.get('resourceType')
    old_id=value.get('id')
    if isinstance(old_id,str):
     if contained and '#'+old_id in local_ids:value['id']=local_ids['#'+old_id][1:]
     elif isinstance(resource_type,str) and resource_type+'/'+old_id in id_map:value['id']=id_map[resource_type+'/'+old_id]
    for key,child in list(value.items()):
     if key=='reference' and isinstance(child,str):
      if child in local_ids:value[key]=local_ids[child]
      elif child in full_url_map:value[key]=full_url_map[child]
      else:
       target=_reference_target(child,full_urls,resources)
       if target is not None:
        target_resource=entries[target]['resource'];target_type=target_resource.get('resourceType');target_id=target_resource.get('id')
        mapped=id_map.get(target_type+'/'+target_id) if isinstance(target_id,str) else None
        value[key]=target_type+'/'+mapped if mapped else next((full_url_map[url] for url,index in full_urls.items() if index==target),child)
     elif key=='fullUrl' and isinstance(child,str) and child in full_url_map:value[key]=full_url_map[child]
     elif key=='contained' and isinstance(child,list):
      for item in child:remap(item,local_ids,True)
     else:remap(child,local_ids,contained)
   elif isinstance(value,list):
    for child in value:remap(child,local_ids,contained)

  cleaned={}
  for key,value in v.items():
   if key!='entry':cleaned.update(self.clean({key:value},None,resource='Bundle',monthfirst=monthfirst))
  cleaned_entries=[]
  for index,entry in enumerate(entries):
   record_index=ownership.get(index);record=records[record_index] if record_index is not None else None
   clean_entry={}
   for key,value in entry.items():
    if key=='resource':
     clean_entry[key]=self.clean(value,record,resource=value.get('resourceType',''),monthfirst=monthfirst)
    elif key=='fullUrl':
     clean_entry[key]=value
    else:
     clean_entry[key]=self.clean(value,record,parents=('entry',key),resource='Bundle',monthfirst=monthfirst)
   resource=clean_entry.get('resource',{})
   local_ids=contained_ids(entry['resource'])
   remap(clean_entry,local_ids)
   if resource.get('resourceType')=='Patient' and record and record.key:
    resource.setdefault('identifier',[]).append({'system':'urn:sheild:patient','value':self.token(record.key)})
   cleaned_entries.append(clean_entry)
  cleaned['entry']=cleaned_entries
  remap(cleaned)
  return cleaned
 def output_path(self,d,used):
  p=PurePosixPath(d.path);parts=[]
  for part in p.parts[:-1]:
   sensitive=(self.rx and self.rx.search(part.replace('_',' '))) or any(rx.search(part) for _,rx in PATTERNS)
   parts.append(self.token(part,'dir').lower() if sensitive else part)
  stem=p.stem; sensitive=(self.rx and self.rx.search(stem.replace('_',' '))) or any(rx.search(stem.replace('_',' ')) for _,rx in PATTERNS) or bool(re.search(r'(?i)(?:patient|discharge_summary)[_-][A-Za-z\u0900-\u097f]+[_-][A-Za-z\u0900-\u097f]+',stem))
  name=self.token(d.path,'doc').lower()+d.fmt if sensitive else (p.stem+d.fmt if p.suffix.lower()!=d.fmt else p.name)
  out='sanitized/'+ '/'.join(parts+[name]);
  if out.casefold() in used:out='sanitized/'+ '/'.join(parts+[self.token(d.path,'doc').lower()+p.suffix])
  used.add(out.casefold());return out
 def render(self,d):
  if d.fmt in ('.csv','.tsv'):
   h=[self.token(k,'KEY') if ID.search(k) or (self.rx and self.rx.search(k) and field_role(k)=='text') else k for k in d.header]
   buf=io.StringIO();w=csv.writer(buf,delimiter=d.delimiter,lineterminator='\n');w.writerow(h)
   for r in d.records:
    vals=[self.clean_text(str(r.value[k]),r,field_role(k),d.monthfirst or 'mmdd' in nk(k)) for k in d.header]
    if r.key and self.token(r.key) not in vals:r.key=None # do not assert absent pseudonyms
    w.writerow(vals)
   return buf.getvalue()
  if d.fmt=='.txt':
   r=d.records[0];t=self.clean_text(d.data,r,monthfirst=d.monthfirst)
   if r.key:t='Patient reference: '+self.token(r.key)+'\n'+t
   return t
  if isinstance(d.data,dict) and d.data.get('resourceType')=='Bundle':return json.dumps(self.fhir(d.data,d.records,d.fhir_ownership,d.monthfirst),ensure_ascii=False,indent=2)+'\n'
  byobj={id(r.value):r for r in d.records}
  def walk(v,parents=()):
   if id(v) in byobj:
    r=byobj[id(v)];x=self.clean(v,r,parents,monthfirst=d.monthfirst)
    if r.key and isinstance(x,dict):x.setdefault('patient_ref',self.token(r.key))
    if r.key and self.token(r.key) not in json.dumps(x):r.key=None
    return x
   if isinstance(v,dict):
    result={}
    for k,x in v.items():
     if not isinstance(x,(dict,list)):
      result.update(self.clean({k:x},None,parents,monthfirst=d.monthfirst))
     else:result[k]=walk(x,parents+(k,))
    return result
   if isinstance(v,list):return [walk(x,parents) for x in v]
   return self.clean(v,parents=parents,monthfirst=d.monthfirst)
  return json.dumps(walk(d.data),ensure_ascii=False,indent=2)+'\n'

def load_model(required=True):
 try:
  from models.v2.model_runtime import CandidateModels
  return CandidateModels()
 except (ImportError,OSError,ValueError,RuntimeError):
  if required:raise RuntimeError('model_unavailable') from None
  return None

def run_pipeline(entries,out,secret,model,stage=lambda *a:None):
 start=time.monotonic();memory=isinstance(out,dict)
 if not memory:
  out=Path(out);san=out/'sanitized';san.mkdir(parents=True,exist_ok=False)
 def emit(name,text):
  if memory:out[name]=text.encode('utf-8')
  else:
   dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text,encoding='utf-8',newline='')
 docs=[];files=[];allrecords=[];total=0;seenpaths=set()
 stage('ingestion','running')
 for path,raw in entries:
  if not isinstance(raw,bytes):raise ValueError('invalid_content')
  total+=len(raw)
  if total>MAX_TOTAL or len(files)>=MAX_FILES:raise ValueError('dataset_limit')
  entry={'input_sha256':hashlib.sha256(raw).hexdigest(),'output':None,'status':'quarantined'};files.append(entry)
  try:
   path_key=_safe_input_path(path)
   if path_key in seenpaths:raise ValueError('duplicate_path')
   seenpaths.add(path_key)
   d=parse(path,raw);docs.append((d,entry));
   for r in d.records:r.shift_key='unlinked:'+d.digest+':'+r.loc
   allrecords.extend(d.records)
  except (ValueError,RecursionError,UnicodeError,csv.Error,TypeError,KeyError,OverflowError) as e:
   entry['reason']=str(e) if type(e) is ValueError and str(e) in SAFE_QUARANTINE_REASONS else 'invalid_content'
 stage('ingestion','completed');stage('normalization','completed');stage('pii-detection','running')
 engine=Engine(secret,model);engine.build_vocab(allrecords);stage('pii-detection','completed');stage('identity-resolution','running');linker=Linker(allrecords,model);linker.run();engine.prepare_shifts([d for d,_ in docs]);stage('identity-resolution','completed');stage('transformation','running')
 records=[];used=set();processed=[]
 for d,entry in docs:
  try:
   d.output=engine.output_path(d,used);result=engine.render(d)
   if d.fmt=='.json':json.loads(result)
   emit(d.output,result)
   entry.update(output=d.output,status='sanitized');processed.append(d)
   for r in d.records:
    if r.evidence.has():records.append({'file':d.output,'loc':r.loc,'patient':engine.token(r.key) if r.key else None,'status':'generalized' if r.generalized else 'sanitized'})
  except (ValueError,RecursionError,UnicodeError,csv.Error,TypeError,KeyError,OverflowError):entry.update(output=None,status='quarantined',reason='unsafe_transformation')
 stage('transformation','completed')
 counts={'files_total':len(files),'files_sanitized':sum(x['status']=='sanitized' for x in files),'files_quarantined':sum(x['status']=='quarantined' for x in files),'records_processed':len(records),'identifiers_detected':sum(engine.entities.values()),'records_linked':sum(r['patient'] is not None for r in records),'records_generalized':sum(r['status']=='generalized' for r in records),'records_suppressed':0,'records_quarantined':0}
 try:
  import resource,sys
  rss=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1048576 if sys.platform=='darwin' else 1024),2)
 except ImportError:
  try:
   import psutil
   m=psutil.Process().memory_info();rss=round(m.peak_wset/1048576,2) if hasattr(m,'peak_wset') else None
  except ImportError:rss=None
 report={'schema':'raksha-report/1','files':files,'counts':counts,'entities':dict(sorted(engine.entities.items())),'timing':{'seconds':round(time.monotonic()-start,3)},'resources':{'peak_rss_mb':rss},'risk_proxy':linker.risk_summary}
 emit('report.json',json.dumps(report,ensure_ascii=False,indent=2)+'\n');emit('records.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
 return report,processed

def directory_entries(inp):
 def is_reparse(st):
  return stat.S_ISLNK(st.st_mode) or bool(getattr(st,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0x400))
 def open_no_follow(path):
  if os.name!='nt':
   return os.fdopen(os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)),'rb')
  import ctypes,msvcrt
  from ctypes import wintypes
  kernel32=ctypes.WinDLL('kernel32',use_last_error=True);create_file=kernel32.CreateFileW
  create_file.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
  create_file.restype=wintypes.HANDLE
  handle=create_file(str(path),0x80000000,0x00000001,None,3,0x00200000|0x08000000,None)
  if handle==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_last_error(),'input_open_failed')
  try:fd=msvcrt.open_osfhandle(int(handle),os.O_RDONLY|os.O_BINARY)
  except Exception:
   kernel32.CloseHandle(handle)
   raise
  return os.fdopen(fd,'rb')
 root=Path(inp)
 root_stat=root.lstat()
 if is_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):raise ValueError('invalid_input_directory')
 pending=[(root,'')];files=[];expected_total=0;directory_count=1;entry_count=0
 while pending:
  directory,prefix=pending.pop()
  with os.scandir(directory) as scan:
   children=[]
   for item in scan:
    entry_count+=1
    if entry_count>MAX_DIRECTORY_ENTRIES:raise ValueError('dataset_limit')
    children.append(item)
   children.sort(key=lambda item:(item.name.casefold(),item.name))
  for item in children:
   relative=(prefix+'/'+item.name) if prefix else item.name
   _safe_input_path(relative)
   st=Path(item.path).lstat()
   if is_reparse(st):raise ValueError('symlink_not_allowed')
   if stat.S_ISDIR(st.st_mode):
    directory_count+=1
    if directory_count>MAX_DIRECTORIES:raise ValueError('dataset_limit')
    pending.append((Path(item.path),relative))
   elif stat.S_ISREG(st.st_mode):
    files.append((relative,Path(item.path),st))
    expected_total+=st.st_size
    if len(files)>MAX_FILES or expected_total>MAX_TOTAL:raise ValueError('dataset_limit')
   else:raise ValueError('unsupported_file_type')
 actual_total=0
 for relative,path,expected in sorted(files,key=lambda item:(item[0].casefold(),item[0])):
  if expected_total>MAX_TOTAL or expected.st_size>MAX_TOTAL:raise ValueError('dataset_limit')
  with open_no_follow(path) as stream:
   before=os.fstat(stream.fileno())
   if is_reparse(before) or not stat.S_ISREG(before.st_mode):raise ValueError('symlink_not_allowed')
   if (before.st_dev,before.st_ino,before.st_size)!=(expected.st_dev,expected.st_ino,expected.st_size):raise ValueError('input_changed')
   chunks=[];size=0;limit=MAX_TOTAL-actual_total
   while True:
    chunk=stream.read(min(65536,limit-size+1))
    if not chunk:break
    size+=len(chunk)
    if size>limit:raise ValueError('dataset_limit')
    chunks.append(chunk)
   after=os.fstat(stream.fileno())
   if is_reparse(after) or (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)!=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) or size!=after.st_size:raise ValueError('input_changed')
  actual_total+=size
  yield relative,b''.join(chunks)
