"""Unit test for compute_next_last_seen — the stuck-placeholder fix.

Run: /Users/wangtingwei/opt/anaconda3/bin/python test_advance.py
"""
import importlib.util

s = importlib.util.spec_from_file_location("au", "auto_update.py")
au = importlib.util.module_from_spec(s)
s.loader.exec_module(au)
f = au.compute_next_last_seen

OK = "audio+llm"
FAIL = "audio-pending"

cases = [
    (665, [666], {"666": {"auto_status": OK}}, 666, "success advances"),
    (665, [666], {"666": {"auto_status": FAIL}}, 665, "FAILURE stays put (retry next run)"),
    (665, [666, 667], {"666": {"auto_status": OK}, "667": {"auto_status": FAIL}}, 666, "ok then fail: stop after ok"),
    (665, [666, 667], {"666": {"auto_status": FAIL}, "667": {"auto_status": OK}}, 665, "gap at bottom blocks higher ok"),
    (665, [666, 667, 668], {"666": {"auto_status": OK}, "667": {"auto_status": OK}, "668": {"auto_status": FAIL}}, 667, "two ok then fail"),
    (665, [], {}, 665, "no candidates"),
]

allok = True
for ls, cand, eps, exp, label in cases:
    got = f(ls, cand, eps)
    ok = got == exp
    allok &= ok
    print(("PASS" if ok else "FAIL"), f"got={got} exp={exp}", "|", label)
print("ALL_PASS" if allok else "SOME_FAILED")
