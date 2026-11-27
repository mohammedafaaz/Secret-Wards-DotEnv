import hashlib
import os

files = [
    'sheild/engine.py',
    'sheild/verify.py',
    'models/v2/model_runtime.py',
    'models/v2/model_features.py',
    'main.py',
    'raksha.toml'
]

print('Protected file hashes:')
for f in files:
    if os.path.exists(f):
        with open(f, 'rb') as fp:
            h = hashlib.sha256(fp.read()).hexdigest()[:16]
            print(f'{f}: {h}')
    else:
        print(f'{f}: NOT FOUND')