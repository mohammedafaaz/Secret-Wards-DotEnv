"""Shared training/inference feature contract, version 1. No patient-specific dictionary."""
import re, unicodedata as u
from difflib import SequenceMatcher
VERSION = '1.0'

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

def features(tokens):
    words=[t[0] if isinstance(t,(list,tuple)) else t for t in tokens]; result=[]
    for i,w in enumerate(words):
        n=norm(w); f={'bias':1.,'shape':token_shape(w),'script':'dev' if any('\u0900'<=c<='\u097f' for c in w) else 'other','length':str(min(len(w),12)),'digit':w.isdecimal(),'upper':w.isupper(),'title':w.istitle(),'prefix2':n[:2],'suffix2':n[-2:],'suffix3':n[-3:]}
        # Lexical cues for nearby labels/clinical context, not a full name gazetteer.
        for j in (-3,-2,-1,1,2,3):
            if 0<=i+j<len(words):
                v=words[i+j]; f[f'{j}:word']=norm(v); f[f'{j}:shape']=token_shape(v)
            else: f[f'{j}:boundary']=True
        result.append(f)
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

def comparison(a,b):
    def exact(k):
        x,y=norm(str(a.get(k) or '')).strip(),norm(str(b.get(k) or '')).strip()
        return 'missing' if not x or not y else 'agree' if x==y else 'conflict'
    def sim(k):
        v=similarity(a.get(k) or '',b.get(k) or '')
        return 'missing' if v is None else 'high' if v>=.88 else 'medium' if v>=.60 else 'low'
    same_h=exact('hospital')=='agree'
    return {'name':sim('name'),'relative':sim('relative'),'dob':exact('dob'),'phone':exact('phone'),'village':exact('village'),'local_id':exact('local_id') if same_h else 'missing','strong_id':exact('strong_id')}

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
