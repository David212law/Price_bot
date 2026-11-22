"""Agent self-test — verify all fixers on known patterns."""
import sys, os, tempfile, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import agent

PASS, FAIL = 0, 0
def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; print(f"✅ {name}")
    else: FAIL += 1; print(f"❌ {name}")

# ══ Test 1: 5 original fixers ══
test1 = '''def foo(x):
    if x == None:
        return 1
    if x != None:
        try:
            pass
        except:
            pass
    return None'''
f = pathlib.Path("/data/data/com.termux/files/home/Price_bot/m12/_st1.py")
f.write_text(test1)
agent.fix_eof_newline(f)
agent.fix_none_comparison(f)
agent.fix_bare_except(f)
result = f.read_text()
check("None comparison", "x is None" in result)
check("Not-None comparison", "x is not None" in result)
check("bare except", "except Exception:" in result)
f.unlink()

# ══ Test 2: dict.keys() ══
test2 = '''d = {"a": 1}
if "a" in d.keys():
    pass
if "b" not in d.keys():
    pass'''
f = pathlib.Path("/data/data/com.termux/files/home/Price_bot/m12/_st2.py")
f.write_text(test2)
agent.fix_dict_keys_membership(f)
result = f.read_text()
check("dict.keys() removed", ".keys()" not in result)

# ══ Test 3: not in ══
test3 = '''x = 1
if not x in [2, 3]:
    pass'''
f = pathlib.Path("/data/data/com.termux/files/home/Price_bot/m12/_st3.py")
f.write_text(test3)
agent.fix_not_in(f)
result = f.read_text()
check("not in fixed", "x not in" in result)
f.unlink()

# ══ Test 4: undefined names ══
test4 = '''import os
def foo():
    return os.path.exists("x") and undefined_var'''
f = pathlib.Path("/data/data/com.termux/files/home/Price_bot/m12/_st4.py")
f.write_text(test4)
un = agent.undefined_names(str(f))
check("undefined detected", len(un) > 0 and "undefined_var" in [u[1] for u in un])
f.unlink()

print(f"\n{'='*50}")
print(f"PASS: {PASS}, FAIL: {FAIL}")
print(f"{'='*50}")
sys.exit(0 if FAIL == 0 else 1)
