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


# Test 5: while 1
f = w("_t5.py", "def go():\n    while 1:\n        pass\n")
agent.fix_while_1(f)
check("while 1 -> while True", "while True:" in f.read_text())

# Test 6: len truthiness
f = w("_t6.py", "if len(x) > 0:\n    pass\nif len(y) == 0:\n    pass\n")
agent.fix_len_truthiness(f)
r = f.read_text()
check("len(x)>0 -> x", "if x:" in r)
check("len(y)==0 -> not y", "if not y:" in r)

# Test 7: verbose True/False
f = w("_t7.py", "if a == True:\n    pass\nif b == False:\n    pass\n")
agent.fix_verbose_true(f)
r = f.read_text()
check("x==True -> x", "if a:" in r)
check("x==False -> not x", "if not b:" in r)

print("\n" + "="*50)
print(f"PASS: {PASS}, FAIL: {FAIL}")
print("="*50)
sys.exit(0 if FAIL == 0 else 1)
