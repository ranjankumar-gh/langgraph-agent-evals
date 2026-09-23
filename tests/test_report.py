from evals.report import passes, rate, summarize, wilson


def run(variant, *, answer=True, end=True, cons=True, modes=None, fired=(), slice_="happy", crashed=None):
    return {
        "case_id": "X", "slice": slice_, "variant": variant, "trial": 0, "crashed": crashed,
        "answer_pass": answer, "end_state_pass": end, "constraints_pass": cons,
        "mode_pass": modes or {"strict": True, "unordered": True, "subset": True, "superset": True},
        "mutations_fired": list(fired),
    }


def test_wilson_bounds():
    low, high = wilson(5, 10)
    assert 0.23 < low < 0.24 and 0.76 < high < 0.77
    assert wilson(0, 0) == (0.0, 0.0)


def test_crashed_runs_pass_nothing():
    assert not passes(run("baseline", crashed="Boom"), "answer_only")


def test_summary_rates():
    runs = [
        run("A", cons=False, fired=["A:skipped_eligibility"]),          # blind pass
        run("A", end=False, answer=False, fired=["A:skipped_eligibility"]),  # caught by everything
        run("A"),                                                       # fault did not fire: excluded from survival
        run("alt_recheck", modes={"strict": False, "unordered": False, "subset": True, "superset": True}),
        run("baseline"),
    ]
    s = summarize(runs)
    assert s["mutant_survival"]["A"]["answer_only"]["k"] == 1
    assert s["mutant_survival"]["A"]["answer_only"]["n"] == 2
    assert s["mutant_survival"]["A"]["three_artifact"]["k"] == 0
    assert s["tbp"]["A"]["k"] == 1 and s["tbp"]["A"]["n"] == 2
    assert s["brittle_fail"]["alt_recheck"]["strict"]["k"] == 1
    assert s["brittle_fail"]["alt_recheck"]["constraints"]["k"] == 0
    assert s["brittle_fail"]["baseline"]["strict"]["k"] == 0
    assert rate(1, 4)["rate"] == 0.25
