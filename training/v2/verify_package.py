"""Non-CRF smoke tests, input data integrity and training/runtime policy consistency."""
import collections, json
from pathlib import Path
from train_models import verify,read
from model_features import tokenize,span_labels,decode,features,comparison,eligible
base=Path(__file__).resolve().parent; data=base/'data'; verify(data)
ids=set(); families=set(); summary={}
for s in ('train','validation','test'):
    counts=collections.Counter(); lang=collections.Counter(); local=set()
    for r in read(data/f'ner_{s}.jsonl'):
        assert r['id'] not in ids; ids.add(r['id']); local.add(r['family']); lang[r['language']]+=1
        t,l=span_labels(r['text'],r['spans']); assert decode(t,l)==r['spans']; counts.update(x['label'] for x in r['spans'])
    assert not families.intersection(local); families.update(local)
    summary[s]={'ner_examples':sum(lang.values()),'languages':dict(lang),'unique_composed_patterns':len(local),'entity_counts':dict(counts)}
assert len(features(tokenize('आयु ४५ वर्ष; BP 120/80 mmHg')))==len(tokenize('आयु ४५ वर्ष; BP 120/80 mmHg'))
a={'name':'Amit Sharma','phone':'0000012345','dob':'1980-12-31'}; b={'name':'Sharma Amit','phone':'+91 00000-12345','dob':'31/12/1980'}
f=comparison(a,b); assert f['phone']==f['dob']=='agree' and eligible(f)
assert not eligible(comparison({'name':'Amit Sharma','phone':'0000012345'},{'name':'Amit Sharma','phone':'0000012345'}))
assert not eligible(comparison({'strong_id':'ABC','dob':'1980-12-31'},{'strong_id':'ABC','dob':'1981-12-31'}))
print(json.dumps(summary,ensure_ascii=False,indent=2))
