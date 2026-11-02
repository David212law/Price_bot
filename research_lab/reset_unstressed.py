import json, os
p = 'research_lab/logs/profiles/state.json'
if not os.path.exists(p):
    print("No state file.")
    exit(0)
d = json.load(open(p))
before = len(d['done'])
# فقط آنهایی را نگه دار که stress دارند
d['done'] = {k: v for k, v in d['done'].items()
             if isinstance(v, str) or v.get('validation', {}).get('stress', {})}
after = len(d['done'])
json.dump(d, open(p, 'w'), indent=2, default=str)
print(f'✅ Kept {after} stressed entries, removed {before - after} unstressed.')
