"""Agent self-test — verify all fixers on known patterns.
Uses a temp dir so it runs on any machine (Termux/GitHub)."""
import sys, os, tempfile, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import agent

TMP = pathlib.Path(tempfile.mkdtemp(prefix="agent_st_"))
PASS, FAIL = 0, 0
def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; print(f"OK  {name}")
    else: FAIL += 1; print(f"FAIL {name}")

def w(name, text):
    f = TMP / name; f.write_text(text); return f

# Test 1: None comparison + bare except + eof newline
f = w("_t1.py", '''def foo(x):
    if x == None:
        return 1
    if x != None:
        try:
            pass
        except:
            pass
    return None''')
agent.fix_eof_newline(f)
agent.fix_none_comparison(f)
agent.fix_bare_except(f)
r = f.read_text()
check("None comparison", "x is None" in r)
check("Not-None comparison", "x is not None" in r)
check("bare except", "except Exception:" in r)

# Test 2: dict.keys()
f = w("_t2.py", '''d = {"a": 1}
if "a" in d.keys():
    pass
if "b" not in d.keys():
    pass''')
agent.fix_dict_keys_membership(f)
r = f.read_text()
check("dict.keys() removed", ".keys()" not in r)

# Test 3: not in
f = w("_t3.py", '''x = 1
if not x in [2, 3]:
    pass''')
agent.fix_not_in(f)
check("not in fixed", "x not in" in f.read_text())

# Test 4: undefined names
f = w("_t4.py", '''import os
def foo():
    return os.path.exists("x") and undefined_var''')
un = agent.undefined_names(str(f))
check("undefined detected", len(un) > 0 and "undefined_var" in [u[1] for u in un])

print("\n" + "="*50)
print(f"PASS: {PASS}, FAIL: {FAIL}")
print("="*50)
sys.exit(0 if FAIL == 0 else 1)
