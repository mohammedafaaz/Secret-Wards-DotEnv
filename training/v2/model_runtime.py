"""Offline model adapter; candidate spans and pair scores, NOT a release verifier."""
import json,math
from pathlib import Path
try: from .model_features import VERSION,tokenize,features,decode,comparison,eligible
except ImportError: from model_features import VERSION,tokenize,features,decode,comparison,eligible
HERE=Path(__file__).resolve().parent
class CandidateModels:
    def __init__(self,model_dir=HERE):
        import pycrfsuite
        p=Path(model_dir); meta=json.loads((p/'model_metadata.json').read_text()); self.params=json.loads((p/'linkage_parameters.json').read_text())
        if meta['feature_version']!=VERSION or self.params['feature_version']!=VERSION or not meta['ner_trained']: raise ValueError('Model contract mismatch')
        self.tagger=pycrfsuite.Tagger(); self.tagger.open(str(p/'pii_crf.crfsuite'))
    def spans(self,text):
        tok=tokenize(text)
        if not tok: return []
        if len(tok)>4096: raise ValueError('Input exceeds model sequence budget; bounded segmentation required')
        return decode(tok,self.tagger.tag(features(tok)))
    def pair(self,a,b):
        f=comparison(a,b); score=sum(self.params['weights'][k][v] for k,v in f.items()); th=self.params['threshold']
        conflict=any(f[k]=='conflict' for k in ('strong_id','dob','local_id'))
        accepted=eligible(f)
        return {'score':score,'candidate_link':bool(accepted and th is not None and score>=th),'conflict':conflict}
