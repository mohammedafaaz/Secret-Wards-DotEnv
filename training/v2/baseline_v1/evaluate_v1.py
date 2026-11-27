"""Evaluate the frozen V1 models on exactly the V2 test records. Run as a separate process."""
import argparse,json
from pathlib import Path
import train_models as t
from model_features import comparison
p=argparse.ArgumentParser(); p.add_argument('--data',type=Path,required=True); p.add_argument('--output',type=Path,required=True); p.add_argument('--linkage-only',action='store_true'); a=p.parse_args(); here=Path(__file__).resolve().parent
params=json.loads((here/'linkage_parameters.json').read_text()); rows=[(comparison(r['left'],r['right']),r['same_patient'],r['scenario']) for r in t.read(a.data/'linkage_test.jsonl')]; result={'linkage':t.eval_pairs(rows,params,params['threshold'])}
if not a.linkage_only:
 import pycrfsuite
 tag=pycrfsuite.Tagger(); tag.open(str(here/'pii_crf.crfsuite')); result['ner']=t.evaluate_ner(tag,t.read(a.data/'ner_test.jsonl'))
a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
