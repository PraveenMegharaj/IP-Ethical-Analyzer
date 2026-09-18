"""Lightweight checks for the FAIR-R2L de-duplication and Trust parking.

Run: python test_refactor.py   (no pytest needed)
"""

import sys

from fair_r2l_scorer import FAIRR2LScorer, FAIR_DIMENSIONS

FAILS = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        FAILS.append(name)


def fuji(findable, accessible, interoperable, reusable, from_fuji=True):
    def dim(p, level):
        return {"earned": None, "total": None, "percent": p,
                "maturity": None, "level": level}
    return {
        "dimensions": {
            "findable": dim(findable, "Moderate"),
            "accessible": dim(accessible, "Moderate"),
            "interoperable": dim(interoperable, "Advanced"),
            "reusable": dim(reusable, "Initial"),
        },
        # A populated 'principles' map signals a real F-UJI run.
        "principles": {"F1": {}} if from_fuji else {},
        "is_estimate": (not from_fuji),
        "overall": {"percent": (findable + accessible + interoperable + reusable) / 4},
    }


ARTEFACT = {
    "licence_string": "CC BY 4.0",
    "title": "Beijing Air-Quality Sensor Readings",
    "doi": "10.5281/zenodo.8214839",
    "authors": ["Zhang, L.", "Wang, H."],
    "files": [{"name": "data.csv"}, {"name": "data.json"}],
    "access_right": "open",
}

scorer = FAIRR2LScorer()

# --- 1. FAIR is consumed from F-UJI, not re-derived ------------------------
res = scorer.score(ARTEFACT, fair_result=fuji(57.14, 42.86, 100.0, 50.0))
secs = res["sections"]

for key in FAIR_DIMENSIONS:
    check(f"FAIR dimension present: {key}", key in secs)
check("findable readiness == F-UJI value", secs["findable"]["readiness"] == 57.14)
check("interoperable readiness == F-UJI value", secs["interoperable"]["readiness"] == 100.0)
check("FAIR source flagged f-uji", secs["findable"]["source"] == "f-uji")
check("fair_source top-level == f-uji", res["fair_source"] == "f-uji")

# R2L-specific dimensions still come from the checklist
check("ai_readiness section present", "ai_readiness" in secs)
check("responsible_licensing section present", "responsible_licensing" in secs)

# Overall = equal-weight mean of every dimension that has a readiness
vals = [s["readiness"] for s in secs.values() if s["readiness"] is not None]
expected = round(sum(vals) / len(vals), 2)
check("overall readiness = mean of all dimensions", res["readiness"] == expected)

# --- 2. Changing F-UJI changes FAIR (proves it is consumed) ----------------
res2 = scorer.score(ARTEFACT, fair_result=fuji(10.0, 10.0, 10.0, 10.0))
check("FAIR readiness follows F-UJI (low)", res2["sections"]["findable"]["readiness"] == 10.0)
check("overall drops when F-UJI drops", res2["readiness"] < res["readiness"])

# --- 3. Metadata fallback is flagged ---------------------------------------
res3 = scorer.score(ARTEFACT, fair_result=fuji(60, 60, 60, 60, from_fuji=False))
check("metadata fallback flagged", res3["fair_source"] == "metadata-fallback")

# --- 3b. Fallback reports dimensions as bare numbers, not dicts ------------
resf = scorer.score(ARTEFACT, fair_result={
    "dimensions": {"findable": 40.0, "accessible": 25.0,
                   "interoperable": 0.0, "reusable": 0.0},
    "is_estimate": True,
})
check("float-shaped FAIR dimension handled", resf["sections"]["findable"]["readiness"] == 40.0)
check("float-shape flagged metadata-fallback", resf["fair_source"] == "metadata-fallback")

# --- 4. Checklist no longer carries FAIR sections --------------------------
cl_ids = [s["id"] for s in scorer.checklist["sections"]]
check("checklist has no FAIR sections", not (set(cl_ids) & set(FAIR_DIMENSIONS)))
check("checklist keeps ai_readiness + responsible_licensing",
      set(cl_ids) == {"ai_readiness", "responsible_licensing"})

# --- 5. Trust parked: importing the main path does not load transformers ---
import unified_analysis  # noqa: E402
check("transformers NOT imported by main path", "transformers" not in sys.modules)
trust = unified_analysis.analyze_trust("some text " * 10, [])
check("analyze_trust returns disabled by default", trust["band"] == "disabled")

print()
if FAILS:
    print("FAILED:", FAILS)
    sys.exit(1)
print("ALL CHECKS PASSED")
