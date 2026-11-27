"""Reproducible, independently authored synthetic training data. No toolkit access."""
import argparse,json,random,datetime,hashlib,re
from pathlib import Path
from model_features import span_labels
SEED=271127
# The spelling pairs and template families are disjoint by split.
VILLAGES={'train':[('Navapur','नवापुर'),('Udaynagar','उदयनगर'),('Devgaon','देवगांव')],'validation':[('Kesarwadi','केसरवाड़ी'),('Surajpur','सूरजपुर')],'test':[('Nirmalwadi','निर्मलवाड़ी'),('Chandgaon','चांदगांव')]}
CLIN={'en':['Ramipril 5 mg OD; BP 120/80 mmHg','Dolo 650 BD x 5 days; Hb 11.2 g/dL','Parkinson disease; physiotherapy 1-0-1','SpO2 97%; glucose 108 mg/dL','Metformin 500 mg BID; pulse 78 bpm','Dengue; stay 9 days; platelets 140000 /µL'], 'hi':['रैमिप्रिल 5 mg रोज; बीपी 120/80 mmHg','बुखार; डोलो 650 mg दिन में दो बार','हीमोग्लोबिन 11.2 g/dL; नाड़ी 78 bpm','मधुमेह; ग्लूकोज़ 108 mg/dL','डेंगू; भर्ती 9 दिन; प्लेटलेट 140000 /µL','पार्किंसन रोग; फिजियोथेरेपी'], 'mix':['BP 120/80 mmHg; दवा Ramipril 5 mg OD','Dolo 650 BD x 5 days; बुखार','Hb 11.2 g/dL, नाड़ी 78 bpm','sugar 108 mg/dL; मधुमेह','dengue ka stay 9 days; platelet 140000 /µL','Parkinson disease; दवा 1-0-1']}
LABELS={'patient':'PATIENT','relative':'RELATIVE','phone':'PHONE','id':'ID','date':'DATE','address':'ADDRESS','email':'EMAIL','age':'AGE','pin':'PIN','doctor':'DOCTOR','clinical':'CLINICAL','complaint':'CLINICAL'}
# V2 adds independent roots and surnames, alternate name order, initials, and varied clause structures.
ROOTS={"train":"Amit:अमित,Anu:अनु,Bha:भा,Chandra:चंद्र,Daya:दया,Esha:ईशा,Giri:गिरि,Hari:हरि,Indu:इंदु,Jaya:जया,Kamal:कमल,Lata:लता,Mani:मणि,Nava:नव,Om:ओम,Pari:परि,Raj:राज,Sar:सर,Tara:तारा,Uday:उदय,Veda:वेदा,Yash:यश,Zain:ज़ैन,Abdul:अब्दुल,Noor:नूर,Shab:शब,Asif:आसिफ,Rehan:रेहान,Megha:मेघा,Shiv:शिव", "validation":"Aksh:अक्ष,Prabha:प्रभा,Ritu:ऋतु,Soh:सोह,Tej:तेज,Naz:नाज़,Salim:सलीम,Uma:उमा,Chait:चैत,Manav:मानव", "test":"Aditya:आदित्य,Bhav:भाव,Dhruv:ध्रुव,Ekta:एकता,Faiz:फ़ैज़,Harsh:हर्ष,Ira:इरा,Jatin:जतिन,Krish:कृष्ण,Lok:लोक,Madhav:माधव,Naaz:नाज़,Rup:रूप,Sur:सुर,Zehra:ज़हरा"}
SUFFIX=[('',''),('deep','दीप'),('raj','राज'),('veer','वीर'),('dev','देव'),('kumar','कुमार'),('mani','मणि'),('nath','नाथ'),('isha','ईशा'),('ansh','अंश'),('ali','अली'),('uddin','उद्दीन'),('jeet','जीत'),('shree','श्री'),('prakash','प्रकाश'),('may','मय'),('preet','प्रीत')]
NEW_SURNAMES={"train":"Sharma:शर्मा,Verma:वर्मा,Patel:पटेल,Iyer:अय्यर,Menon:मेनन,Shetty:शेट्टी,Das:दास,Roy:रॉय,Gupta:गुप्ता,Singh:सिंह,Joshi:जोशी,Pandey:पांडे,Ansari:अंसारी,Ali:अली,Ahmed:अहमद,Syed:सैयद,Rao:राव,Reddy:रेड्डी,Nair:नायर,Prasad:प्रसाद,Bose:बोस,Shah:शाह,Kulkarni:कुलकर्णी,Patil:पाटिल,Chauhan:चौहान,Mehta:मेहता,Saini:सैनी", "validation":"Malik:मलिक,Agarwal:अग्रवाल,Thakur:ठाकुर,Jain:जैन,Naidu:नायडू,Chatterjee:चटर्जी,Shukla:शुक्ला,Trivedi:त्रिवेदी", "test":"Mishra:मिश्रा,Tripathi:त्रिपाठी,Banerjee:बनर्जी,Bhatt:भट्ट,Rawat:रावत,Chandra:चंद्र,Kapadia:कपाड़िया,Hashmi:हाशमी,Shaikh:शेख,Pathak:पाठक,Acharya:आचार्य,Solanki:सोलंकी"}
def pool(s): return [tuple(x.split(':',1)) for x in s.split(',')]
def names(r,s):
    a,b=r.choice(pool(ROOTS[s])); c,d=r.choice(SUFFIX); e,f=r.choice(pool(NEW_SURNAMES[s])); return a+c+' '+e,b+d+' '+f
# Clause banks deliberately have disjoint wording across splits. Compose and shuffle clauses.
BANK={
 'train':{
'en':['patient {patient}','Pt. {patient}','{patient} was seen','S/O {relative}','W/O {relative}','father {relative}','husband {relative}','Age {age} years','aged {age}','{age} yrs','PIN {pin}','pincode {pin}','address {address}','lives at {address}','DOB {date}','admitted {date}','phone {phone}','contact no {phone}','UHID {id}','insurance no {id}','Aadhaar {id}','email {email}','Dr. {doctor}','C/O {complaint}','{clinical}'],
'hi':['रोगी का नाम {patient}','मरीज़ {patient}','पेशेंट {patient}','{patient} जी आए','पिता {relative}','पति का नाम {relative}','परिजन {relative}','पत्नी {relative}','उम्र {age} साल','आयु {age}','{age} वर्ष की आयु','पिन {pin}','पिन कोड {pin}','निवासी {address}','घर का पता {address}','ग्राम {address}','जन्म तिथि {date}','भर्ती {date}','मोबाइल {phone}','संपर्क नंबर {phone}','पंजीकरण संख्या {id}','आभा नंबर {id}','आधार {id}','ईमेल {email}','डॉ. {doctor}','शिकायत {complaint}','{clinical}'],
'mix':['मरीज {patient}','{patient} ji aaye','patient {patient} ka note','{patient} sahab','W/O {relative}','पति {relative}','guardian {relative}','C/O {relative}','उम्र {age} yrs','{age} saal','age {age} साल','PIN code {pin}','पिन {pin}','gaon {address}','घर {address}','janam {date}','admit हुआ {date}','mobile hai {phone}','फोन {phone}','UHID {id}','आधार {id}','mail {email}','Dr. {doctor} ne dekha','C/O {complaint}','{clinical}']},
 'validation':{
'en':['attendee — {patient}','{patient} attended today','caregiver {relative}','next of kin is {relative}','age in years = {age}','{age} years old','postal area {pin}','home locality {address}','birth recorded {date}','callback {phone}','chart reference {id}','correspondence {email}','reviewed by Dr {doctor}','therapy {clinical}','clinical complaint {complaint}'],
'hi':['उपस्थित व्यक्ति {patient}','नाम दर्ज {patient}','देखभालकर्ता {relative}','संबंधी {relative}','वर्षों में आयु {age}','{age} बरस का','डाक क्षेत्र {pin}','रहने का स्थान {address}','जन्म दिनांक {date}','दूरभाष {phone}','अभिलेख क्रमांक {id}','विद्युत डाक {email}','परामर्शदाता डॉ {doctor}','केवल उपचार {clinical}','परेशानी {complaint}'],
'mix':['attendee {patient}','{patient} ka checkup','parijan {relative}','माता {relative}','{age} baras','आयु {age} yrs','postal area {pin}','rehne ki jagah {address}','birth date {date}','call back {phone}','chart ref {id}','correspondence {email}','consultant Dr {doctor}','order दिया {clinical}','परेशानी {complaint}']},
 'test':{
'en':['beneficiary {patient}','{patient} presented at ward','under the care of {relative}','family contact is {relative}','{age} years of age','age recorded as {age}','postal district {pin}','residence near {address}','born on {date}','reach household on {phone}','record code {id}','write to {email}','physician Dr. {doctor}','prescribed {clinical}','reported {complaint}'],
'hi':['लाभार्थी {patient}','{patient} वार्ड में उपस्थित','{relative} की देखरेख में','घरवाले {relative}','{age} वर्ष के','आयु दर्ज {age}','डाक संख्या {pin}','ठिकाना {address}','जन्म हुआ {date}','घर संपर्क {phone}','फाइल संकेत {id}','पत्राचार {email}','निरीक्षण डॉ. {doctor}','तकलीफ और उपचार {clinical}','तकलीफ {complaint}'],
'mix':['beneficiary {patient}','{patient} aaj ward mein','{relative} ke saath','family contact {relative}','{age} साल की उम्र','age recorded {age}','डाक संख्या {pin}','ghar near {address}','born hua {date}','reach on {phone}','record code {id}','पत्राचार {email}','physician डॉ. {doctor}','इलाज noted {clinical}','reported {complaint}']}}
def date(r): return (datetime.date(1940,1,1)+datetime.timedelta(days=r.randrange(30000))).isoformat()
def fmtdate(r,v): return datetime.date.fromisoformat(v).strftime(r.choice(['%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y','%d %b %Y']))
def name_variant(r,p,lang):
    x=p[1] if lang=='hi' or lang=='mix' and r.random()<.5 else p[0]; w=x.split(); mode=r.randrange(8)
    if mode==0: return ' '.join(reversed(w))
    if mode==1 and lang!='hi': return w[0][0]+'. '+w[-1]
    if mode==2: return w[0]
    if mode==3 and lang!='hi': return x.upper()
    return x
def row(r,s,i):
    import string
    lang=['en','hi','mix'][i%3]; bank=BANK[s][lang]; p=names(r,s); rel=names(r,s); doc=names(r,s); v=r.choice(VILLAGES[s]); idx=1 if lang=='hi' else 0
    ph=f'00000{r.randrange(100000):05d}'; ph=r.choice([ph,'+91 '+ph[:5]+' '+ph[5:],ph[:5]+'-'+ph[5:],'('+ph[:5]+') '+ph[5:]])
    clinical=r.choice(CLIN[lang]); clinical=re.sub(r'(?<![\d.])(?:120|108|78|97|140000)(?![\d.])',lambda m:str(max(1,int(m[0])+r.randrange(-5,6))),clinical)
    values={'patient':name_variant(r,p,lang),'relative':name_variant(r,rel,lang),'doctor':name_variant(r,doc,lang),'phone':ph,'id':r.choice([f'EX-{r.randrange(10**7):07d}',f'{r.randrange(10**8):08d}',f'0000 {r.randrange(10000):04d} {r.randrange(10000):04d}',f'XX{r.randrange(10000):04d}X',f'XXXX XXXX {r.randrange(10000):04d}']),'date':fmtdate(r,date(r)),'address':str(r.randrange(1,400))+' '+v[idx]+(' मोहल्ला' if lang=='hi' else ' Colony'),'email':f'v2-{s}-{i}@example.invalid','age':str(r.randrange(1,105)),'pin':str(r.randrange(100000,999999)),'clinical':clinical,'complaint':r.choice(['fever','cough','chest pain'] if lang=='en' else ['बुखार','खांसी','सिरदर्द'] if lang=='hi' else ['fever','खांसी','pet dard'])}
    if lang!='en' and r.random()<.5:
        for k in ['phone','age','pin','date','id']: values[k]=values[k].translate(str.maketrans('0123456789','०१२३४५६७८९'))
    by={}
    for j,t in enumerate(bank):
        k=next(k for _,k,_,_ in string.Formatter().parse(t) if k); by.setdefault(k,[]).append((j,t))
    keys=r.sample(list(by),r.randint(2,5)) if i%10 else r.sample(['clinical','doctor','complaint'],r.randint(1,3))
    if i%10 and i%4==0 and 'clinical' not in keys: keys.append('clinical')
    r.shuffle(keys); chosen=[r.choice(by[k]) for k in keys]; template=r.choice(['; ',' | ','\n',', ',' — ']).join(t for _,t in chosen); text=''; spans=[]
    for literal,key,_,_ in string.Formatter().parse(template):
        text+=literal
        if key is not None:
            a=len(text); text+=values[key]; spans.append({'start':a,'end':len(text),'label':LABELS[key]})
    span_labels(text,spans)
    return {'id':f'v2-{s}-ner-{i:06d}','language':lang,'family':f'{s}/{lang}/'+','.join(str(j) for j,_ in chosen),'text':text,'spans':spans}
def person(r,s,i):
    n=names(r,s); rel=names(r,s); return {'name':n[0],'name_hi':n[1],'relative':rel[0],'relative_hi':rel[1],'dob':date(r),'phone':f'00000{i%100000:05d}','village':r.choice(VILLAGES[s])[0],'hospital':r.choice(['SYN-A','SYN-B','SYN-C','SYN-D']),'local_id':f'EX-{i:07d}','strong_id':f'SYN-UID-{i:08d}'}
def variant(r,p,other_h=False):
    a={k:v for k,v in p.items() if not k.endswith('_hi')}
    if r.random()<.4: a['name']=p['name_hi']
    elif r.random()<.3: a['name']=' '.join(reversed(p['name'].split()))
    if r.random()<.3: a['relative']=p['relative_hi']
    if r.random()<.35: a['dob']=fmtdate(r,p['dob'])
    if r.random()<.45: a['phone']='+91 '+p['phone'][:5]+'-'+p['phone'][5:]
    if other_h: a['hospital']=r.choice([h for h in ['SYN-A','SYN-B','SYN-C','SYN-D'] if h!=p['hospital']]); a['local_id']='OTHER-'+p['local_id']
    for k in ['relative','dob','phone','village','local_id','strong_id']:
        if r.random()<(.65 if k=='strong_id' else .18): a[k]=''
    return a
def pairs(r,s,n):
    for i in range(n):
        base={'train':0,'validation':100000,'test':200000}[s]+i*2; p=person(r,s,base); q=person(r,s,base+1); mode=i%12; same=mode<6
        a=variant(r,p); b=variant(r,p if same else q,other_h=mode in (1,2,3,7,9))
        if mode==2: b['phone']=''; a['strong_id']=b['strong_id']=''
        if mode==3: a['strong_id']=b['strong_id']=''; b['dob']=''; a['phone']=b['phone']=p['phone']; a['relative']=p['relative']; b['relative']=p['relative_hi']
        if mode==4: a['strong_id']=b['strong_id']=''; a['hospital']=b['hospital']=p['hospital']; a['local_id']=b['local_id']=p['local_id']
        if mode==5:
            for k in ['dob','phone','relative','strong_id','local_id','village']: a[k]=b[k]=''
        if mode==6: b['name']=a['name']
        if mode==7: b['phone']=a['phone']; b['name']=a['name']; a['strong_id']=b['strong_id']=''
        if mode==8: b['relative']=a['relative']; b['village']=a['village']
        if mode==9: b['name']=a['name']; b['dob']=a['dob']; b['village']=a['village']; a['strong_id']=b['strong_id']=''; a['phone']=b['phone']=''; a['relative']=b['relative']=''
        if mode==10: b['name']=a['name']; b['phone']=a['phone']; a['strong_id']=p['strong_id']; b['strong_id']=q['strong_id']
        if mode==11: b['name']=a['name']; b['phone']=a['phone']; b['relative']=a['relative']; a['strong_id']=b['strong_id']=''; a['dob']=p['dob']; b['dob']=q['dob']
        yield {'id':f'v2-{s}-pair-{i:06d}','left':a,'right':b,'same_patient':same,'scenario':mode}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path,default=Path('data')); args=ap.parse_args(); args.output.mkdir(parents=True,exist_ok=True); meta={'seed':SEED,'source':'independent compositional synthetic templates v2; no organizer files read','splits':{}}
    for j,(s,n,m) in enumerate([('train',45000,30000),('validation',6000,5000),('test',6000,6000)]):
        r=random.Random(SEED+j); meta['splits'][s]={}
        for kind,items in [('ner',(row(r,s,i) for i in range(n))),('linkage',pairs(r,s,m))]:
            path=args.output/f'{kind}_{s}.jsonl'; count=0
            with path.open('w',encoding='utf-8',newline='\n') as f:
                for obj in items: f.write(json.dumps(obj,ensure_ascii=False,separators=(',',':'))+'\n'); count+=1
            meta['splits'][s][kind]={'count':count,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (args.output/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
