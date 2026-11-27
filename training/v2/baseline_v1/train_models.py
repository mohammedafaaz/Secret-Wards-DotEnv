"""Train CRF and estimate pairwise Fellegi–Sunter-style weights. No evaluation truth access."""
import argparse,collections,hashlib,json,math,shutil,time
from pathlib import Path
from model_features import VERSION,features,span_labels,decode,comparison,tokenize
PII={'PATIENT','RELATIVE','PHONE','ID','ADDRESS','EMAIL','PIN','DATE','AGE'}
PROTECTED={'CLINICAL','DOCTOR'}
def read(p):
    with p.open(encoding='utf-8') as f:
        for line in f: yield json.loads(line)
def write(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def verify(data):
    manifest=json.loads((data/'manifest.json').read_text())
    for s, kinds in manifest['splits'].items():
        for kind,info in kinds.items():
            p=data/f'{kind}_{s}.jsonl'
            if hashlib.sha256(p.read_bytes()).hexdigest()!=info['sha256']: raise ValueError(f'{kind} {s}: checksum mismatch')
            if sum(1 for _ in read(p))!=info['count']: raise ValueError('count mismatch')
    return manifest

def scores(tp,fp,fn):
    p=tp/(tp+fp) if tp+fp else 0.; r=tp/(tp+fn) if tp+fn else 0.
    return {'tp':tp,'fp':fp,'fn':fn,'precision':p,'recall':r,'f1':2*p*r/(p+r) if p+r else 0.}
def evaluate_ner(tagger,rows):
    cnt=collections.defaultdict(lambda:[0,0,0]); lang=collections.defaultdict(lambda:[0,0,0]); protected_n=protected_overlap=0; total=0
    for row in rows:
        tokens=tokenize(row['text']); predicted=decode(tokens,tagger.tag(features(tokens)))
        actual={(x['start'],x['end'],x['label']) for x in row['spans']}; pred={(x['start'],x['end'],x['label']) for x in predicted}
        for label in PII|PROTECTED:
            a={x for x in actual if x[2]==label}; p={x for x in pred if x[2]==label}; vals=(len(a&p),len(p-a),len(a-p))
            for i,v in enumerate(vals): cnt[label][i]+=v
            if label in PII:
                for i,v in enumerate(vals): lang[row['language']][i]+=v
        for a,b,l in actual:
            if l in PROTECTED:
                protected_n+=1; protected_overlap+=any(x<b and y>a and t in PII for x,y,t in pred)
        total+=1
    micro=[sum(cnt[l][i] for l in PII) for i in range(3)]
    return {'examples':total,'pii_exact_span_micro':scores(*micro),'per_label':{l:scores(*cnt[l]) for l in sorted(cnt)},'per_language':{l:scores(*v) for l,v in sorted(lang.items())},'protected_spans':protected_n,'protected_spans_overlapped_by_pii_prediction':protected_overlap,'protected_overlap_rate':protected_overlap/protected_n if protected_n else None}
def train_ner(data,out,iterations):
    import pycrfsuite
    t=pycrfsuite.Trainer(verbose=False)
    for row in read(data/'ner_train.jsonl'):
        tok,tags=span_labels(row['text'],row['spans']); t.append(features(tok),tags)
    t.set_params({'c1':0.15,'c2':0.1,'max_iterations':iterations,'feature.possible_transitions':True})
    t.train(str(out/'pii_crf.crfsuite')); tag=pycrfsuite.Tagger(); tag.open(str(out/'pii_crf.crfsuite'))
    return {s:evaluate_ner(tag,read(data/f'ner_{s}.jsonl')) for s in ('validation','test')}

CATS={'name':['missing','high','medium','low'],'relative':['missing','high','medium','low'],**{k:['missing','agree','conflict'] for k in ['dob','phone','village','local_id','strong_id']}}
def pair_score(params,f): return sum(params['weights'][k][v] for k,v in f.items())
def eligible(f):
    # Shared name/phone alone is insufficient. Exact authoritative conflicts veto the pair.
    if f['strong_id']=='conflict' or f['dob']=='conflict' or f['local_id']=='conflict': return False
    if f['strong_id']=='agree': return True
    supporting=sum([f['dob']=='agree',f['phone']=='agree',f['relative']=='high',f['village']=='agree',f['local_id']=='agree'])
    return (f['name'] in ('high','medium') and supporting>=2 and (f['dob']=='agree' or f['local_id']=='agree' or f['relative']=='high'))
def eval_pairs(rows,params,threshold):
    tp=fp=fn=tn=0; by=collections.defaultdict(lambda:[0,0,0,0])
    for f,y,mode in rows:
        yes=threshold is not None and eligible(f) and pair_score(params,f)>=threshold
        ix=0 if yes and y else 1 if yes else 2 if y else 3
        by[str(mode)][ix]+=1
        if ix==0: tp+=1
        elif ix==1: fp+=1
        elif ix==2: fn+=1
        else: tn+=1
    return {**scores(tp,fp,fn),'tn':tn,'candidate_pairs':tp+fp+fn+tn,'accepted_pairs':tp+fp,'unresolved_pairs':fn+tn,'scenario_counts_tp_fp_fn_tn':dict(by)}
def train_linkage(data,out):
    counts={k:{c:[1,1] for c in cats} for k,cats in CATS.items()}
    for row in read(data/'linkage_train.jsonl'):
        for k,v in comparison(row['left'],row['right']).items(): counts[k][v][int(not row['same_patient'])]+=1
    weights={}
    for k,c in counts.items():
        m=sum(v[0] for v in c.values()); u=sum(v[1] for v in c.values()); weights[k]={v:math.log((n[0]/m)/(n[1]/u)) for v,n in c.items()}
    params={'feature_version':VERSION,'type':'Fellegi-Sunter-style smoothed log likelihood ratios','weights':weights,'threshold':None,'min_validation_precision':.98,'min_validation_accepted':30,'policy':'candidate only; hard conflict veto and independent support; not cluster approval'}
    def split(s): return [(comparison(r['left'],r['right']),r['same_patient'],r['scenario']) for r in read(data/f'linkage_{s}.jsonl')]
    val=split('validation'); test=split('test'); candidates=sorted({pair_score(params,f) for f,_,_ in val if eligible(f)})
    best=None
    for th in candidates:
        result=eval_pairs(val,params,th)
        if result['accepted_pairs']>=30 and result['precision']>=.98:
            if best is None or (result['recall'],result['precision'],th)>(best[0],best[1],best[2]): best=(result['recall'],result['precision'],th)
    if best: params['threshold']=best[2]
    write(out/'linkage_parameters.json',params)
    return {'threshold_selected_on_validation':params['threshold'],'validation':eval_pairs(val,params,params['threshold']),'test':eval_pairs(test,params,params['threshold']),'note':'Synthetic candidate-pair metrics only; not cross-file cluster performance or hidden scores.'}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--data',type=Path,default=Path('data')); ap.add_argument('--output',type=Path,default=Path('export/models')); ap.add_argument('--iterations',type=int,default=65); ap.add_argument('--linkage-only',action='store_true'); args=ap.parse_args(); start=time.monotonic(); manifest=verify(args.data); args.output.mkdir(parents=True,exist_ok=True)
    result={'data_manifest':manifest,'linkage':train_linkage(args.data,args.output)}
    if not args.linkage_only: result['ner']=train_ner(args.data,args.output,args.iterations)
    write(args.output/'evaluation_metrics.json',result)
    import importlib.metadata as md
    write(args.output/'model_metadata.json',{'feature_version':VERSION,'ner_trained':not args.linkage_only,'python_crfsuite_version':None if args.linkage_only else md.version('python-crfsuite'),'training_iterations':args.iterations,'seed':manifest['seed'],'data_source':manifest['source'],'training_seconds':round(time.monotonic()-start,3),'limitations':['Template-generated synthetic data; test performance may overestimate real unseen text performance.','Synthetic IDs and telephone numbers use reserved/test shapes; use separate regex, context and format tests for Indian identifiers.','Linkage features assume canonical normalized attributes; no automatic cluster approval.','No official hidden or practice evaluation performed by this notebook.']})
    for filename in ['model_features.py','model_runtime.py']: shutil.copyfile(Path(__file__).with_name(filename),args.output/filename)
    print(json.dumps({'ner':result.get('ner',{}),'linkage':result['linkage']},indent=2))
if __name__=='__main__': main()
