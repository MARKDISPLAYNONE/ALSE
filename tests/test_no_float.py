"""Guardrail: no float() calls or float literals in engine code (Doc 2 §0). Uses tokenize, so docs/comments are ignored."""
import io
import pathlib
import tokenize

ALLOW = {"engine/decimal_math.py"}  # contains the float *rejection* logic


def offenders(src: str) -> list[str]:
    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    out = []
    for i, t in enumerate(toks):
        if t.type == tokenize.NUMBER and ("." in t.string or "e" in t.string.lower()) and not t.string.lower().startswith("0x"):
            out.append(f"{t.start[0]}:{t.string}")
        if t.type == tokenize.NAME and t.string == "float" and i + 1 < len(toks) and toks[i + 1].string == "(":
            out.append(f"{t.start[0]}:float(")
    return out


def test_no_float_in_engine():
    bad = {}
    for p in pathlib.Path("engine").rglob("*.py"):
        if str(p) in ALLOW:
            continue
        if o := offenders(p.read_text()):
            bad[str(p)] = o
    assert not bad, f"float usage found: {bad}"
