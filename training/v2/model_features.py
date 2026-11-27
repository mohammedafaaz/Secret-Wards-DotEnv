"""Shared training/inference feature contract, version 1. No patient-specific dictionary."""
import re, unicodedata as u, datetime as dt
from difflib import SequenceMatcher
VERSION = '2.0'

def tokenize(text):
    # Keep Unicode letters, combining marks and digits together; retain punctuation.
    out=[]; start=None
    for i,c in enumerate(text):
        if u.category(c)[0] in 'LMN' or c in '\u200c\u200d':
            if start is None: start=i
        else:
            if start is not None: out.append((text[start:i],start,i)); start=None
            if not c.isspace(): out.append((c,i,i+1))
    if start is not None: out.append((text[start:],start,len(text)))
    return out

def norm(s):
    return ''.join(str(u.decimal(c)) if c.isdecimal() else c for c in u.normalize('NFKC',s)).casefold()

def token_shape(s):
    return re.sub(r'(.)\1+',r'\1', ''.join('H' if '\u0900'<=c<='\u097f' and not c.isdecimal() else 'd' if c.isdecimal() else 'X' if c.isupper() else 'x' if c.isalpha() else c for c in s))

# General linguistic cues; not patient-specific names or held-out template lists.
CUES={
 'patient': 'patient pt name रोगी मरीज मरीज़ पेशेंट नाम व्यक्ति लाभार्थी beneficiary attendee',
 'kin': 'father mother husband wife guardian caregiver relative kin son daughter पिता माता पति पत्नी पुत्र पुत्री परिजन संबंधी अभिभावक देखरेख साथ papa parijan',
 'age': 'age aged years year yrs yo old उम्र आयु साल वर्ष बरस saal baras',
 'postal': 'pin pincode postal postcode पिन डाक कोड',
 'address': 'address residence locality village home house colony gaon ग्राम गांव निवासी पता घर मोहल्ला ठिकाना',
 'date': 'dob birth born date admission discharge admitted janam जन्म तिथि दिनांक भर्ती छुट्टी तारीख',
 'phone': 'phone mobile contact callback call reach number मोबाइल संपर्क नंबर दूरभाष फोन',
 'identifier': 'id uhid mrn abha aadhaar insurance code registration chart reference number आधार आभा संख्या पंजीकरण क्रमांक',
 'doctor': 'dr doctor physician consultant चिकित्सक डॉ परामर्शदाता',
 'medical': 'bp hb spo2 glucose mg g dl mmhg ml bpm od bd bid tid dose days fever cough diabetes dengue treatment medicine prescribed complaint बुखार खांसी दवा उपचार शिकायत दिन बीपी हीमोग्लोबिन रोग',
 'honorific': 'ji sahab didi mr mrs shri smt जी साहब श्री श्रीमती'}
CUES={k:set(v.split()) for k,v in CUES.items()}
def features(tokens):
    words=[t[0] if isinstance(t,(list,tuple)) else t for t in tokens]; ns=[norm(w) for w in words]; result=[]
    groups=[{k for k,v in CUES.items() if n in v} for n in ns]
    for i,w in enumerate(words):
        n=ns[i]; f={'bias':1.,'shape':token_shape(w),'script':'dev' if any('\u0900'<=c<='\u097f' for c in w) else 'other','length':str(min(len(w),16)),'digit':n.isdecimal(),'upper':w.isupper(),'title':w.istitle(),'alpha':any(c.isalpha() for c in w),'mixed_digit':any(c.isdecimal() for c in w) and any(c.isalpha() for c in w)}
        for k in (1,2,3,4):
            f[f'pre{k}']=n[:k]; f[f'suf{k}']=n[-k:]
        if n.isdecimal():
            v=int(n); f['age_range']=1<=v<=120; f['digit_count']=str(len(n)); f['year_range']=1900<=v<=2100
        for g in groups[i]: f['cue:'+g]=True
        for j in (-4,-3,-2,-1,1,2,3,4):
            if 0<=i+j<len(words):
                v=words[i+j]; f[f'{j}:word']=ns[i+j]; f[f'{j}:shape']=token_shape(v)
                for g in groups[i+j]: f[f'{j}:cue:{g}']=True; f[f'{"left" if j<0 else "right"}:near:{g}']=True
            else: f[f'{j}:boundary']=True
        # Compact local shape sequences capture phone/date/ID and dosage punctuation.
        f['prev_current_shape']='|'.join(token_shape(x) for x in words[max(0,i-1):i+1]); f['current_next_shape']='|'.join(token_shape(x) for x in words[i:i+2]); result.append(f)
    return result

# Small phonetic transliteration approximation: comparison evidence only, not identity proof.
_CONS=dict(zip('कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसह','k kh g gh n ch chh j jh n t th d dh n t th d dh n p ph b bh m y r l v sh sh s h'.split()))
_VOW=dict(zip('अआइईउऊऋएऐओऔ','a aa i ee u oo ri e ai o au'.split()))
_MARK=dict(zip('ािीुूृेैोौ','aa i ee u oo ri e ai o au'.split()))
def roman(s):
    out=[]; pending=False
    for c in norm(s):
        if c in _CONS:
            if pending: out.append('a')
            out.append(_CONS[c]); pending=True
        elif c in _MARK: out.append(_MARK[c]); pending=False
        elif c=='्': pending=False
        elif c in _VOW:
            if pending: out.append('a')
            out.append(_VOW[c]); pending=False
        elif c in 'ंँ': out.append('n'); pending=False
        elif c=='़': continue
        else:
            if pending and c.isalpha(): out.append('a')
            pending=False; out.append(c)
    # Drop final inherent vowel; rough phonetic feature only.
    return ''.join(out)

def name_key(s):
    v=roman(s); v=re.sub(r'\b(?:mr|mrs|shri|smt|ji|sahab|didi)\b','',v)
    v=v.replace('ph','f').replace('v','w').replace('ee','i').replace('oo','u').replace('aa','a')
    return ''.join(sorted(re.sub(r'[^a-z0-9 ]',' ',v).split()))
def similarity(a,b):
    a,b=name_key(a),name_key(b)
    return SequenceMatcher(None,a,b,autojunk=False).ratio() if a and b else None

def canonical(k,v):
    v=norm(str(v or '')).strip()
    if not v: return ''
    if k=='phone':
        d=re.sub(r'[^0-9]','',v)
        if len(d)==12 and d.startswith('91'): d=d[2:]
        if len(d)==11 and d.startswith('0'): d=d[1:]
        return d if len(d)==10 else ''
    if k=='dob':
        for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y','%d %b %Y'):
            try: return dt.datetime.strptime(v,fmt).date().isoformat()
            except ValueError: pass
        return '' # no ambiguous guesses
    if k in ('local_id','strong_id'): return re.sub(r'\s+','',v)
    return re.sub(r'\s+',' ',v)
def comparison(a,b):
    def exact(k):
        x,y=canonical(k,a.get(k)),canonical(k,b.get(k))
        return 'missing' if not x or not y else 'agree' if x==y else 'conflict'
    def sim(k):
        v=similarity(a.get(k) or '',b.get(k) or '')
        return 'missing' if v is None else 'high' if v>=.86 else 'medium' if v>=.60 else 'low'
    same_h=exact('hospital')=='agree'
    return {'name':sim('name'),'relative':sim('relative'),'dob':exact('dob'),'phone':exact('phone'),'village':exact('village'),'local_id':exact('local_id') if same_h else 'missing','strong_id':exact('strong_id')}
def eligible(f):
    if any(f[k]=='conflict' for k in ('strong_id','dob','local_id')): return False
    if f['strong_id']=='agree': return True
    if f['local_id']=='agree' and (f['name'] in ('high','medium') or f['dob']=='agree'): return True
    if f['name'] not in ('high','medium'): return False
    # Name+DOB+village can still collide; shared phone alone is insufficient.
    return ((f['dob']=='agree' and (f['phone']=='agree' or f['relative']=='high')) or (f['phone']=='agree' and f['relative']=='high' and f['name']=='high'))

def span_labels(text,spans):
    tokens=tokenize(text); labels=[]; prior=None
    for _,a,b in tokens:
        hits=[(i,s) for i,s in enumerate(spans) if a<s['end'] and b>s['start']]
        if len(hits)>1: raise ValueError('overlapping labels')
        if not hits: labels.append('O'); prior=None; continue
        i,s=hits[0]
        if not (s['start']<=a and b<=s['end']): raise ValueError('partial token annotation')
        labels.append(('I-' if prior==i else 'B-')+s['label']); prior=i
    return tokens,labels

def decode(tokens,labels):
    out=[]; active=None
    for (_,a,b),tag in zip(tokens,labels):
        if tag=='O': active=None; continue
        pre,typ=tag.split('-',1)
        if pre=='I' and active and active['label']==typ: active['end']=b
        else: active={'start':a,'end':b,'label':typ}; out.append(active)
    return out
