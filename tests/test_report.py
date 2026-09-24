from evals.report import passes, rate, summarize, wilson


def run(variant, *, answer=True, end=True, cons=True, modes=None, fired=(), slice_="happy", crashed=None, grading_error=None):
    return {
        "case_id": "X", "slice": slice_, "variant": variant, "trial": 0, "crashed": crashed, "grading_error": grading_error,
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


def test_grading_error_excluded_from_rates():
    runs = [
        run("baseline"),
        run("baseline", grading_error="ConnectionError: timeout"),
    ]
    s = summarize(runs)
    assert s["n_runs"] == 1  # grading error run excluded
    assert s["grading_errors"] == 1
    assert s["harness_pass"]["baseline"]["answer_only"]["n"] == 1  # only non-error run counted


def crun(variant, case, trial, **kw):
    r = run(variant, **kw)
    r["case_id"] = case
    r["trial"] = trial
    return r


FIRED_A = ["A:skipped_eligibility"]


def test_mutant_survival_conditioned_on_baseline():
    runs = [
        # pair (P1, 0): baseline passes everything, A passes answer only -> counts, survives answer_only
        crun("baseline", "P1", 0),
        crun("A", "P1", 0, cons=False, fired=FIRED_A),
        # pair (P2, 0): baseline FAILS the answer check; A also fails -> must not count as a kill
        crun("baseline", "P2", 0, answer=False),
        crun("A", "P2", 0, answer=False, fired=FIRED_A),
        # pair (P3, 1): no baseline row at all -> excluded and counted
        crun("A", "P3", 1, answer=False, fired=FIRED_A),
        # pair (P4, 0): baseline passes; A caught by answer -> a kill
        crun("baseline", "P4", 0),
        crun("A", "P4", 0, answer=False, fired=FIRED_A),
    ]
    s = summarize(runs)
    cond = s["mutant_survival"]["A"]
    assert (cond["answer_only"]["k"], cond["answer_only"]["n"]) == (1, 2)
    assert cond["answer_only"]["excluded_no_baseline"] == 1
    assert cond["answer_only"]["excluded_baseline_failed"] == 1
    assert (cond["three_artifact"]["k"], cond["three_artifact"]["n"]) == (0, 2)
    unc = s["mutant_survival_unconditional"]["A"]
    assert (unc["answer_only"]["k"], unc["answer_only"]["n"]) == (1, 4)


def test_slice_mutant_survival_conditioned_on_baseline():
    runs = [
        crun("baseline", "P1", 0, slice_="happy"),
        crun("A", "P1", 0, fired=FIRED_A, slice_="happy"),
        crun("baseline", "P2", 0, answer=False, slice_="happy"),
        crun("A", "P2", 0, answer=False, fired=FIRED_A, slice_="happy"),
    ]
    sl = summarize(runs)["slices"]["happy"]
    assert (sl["mutant_survival"]["answer_only"]["k"], sl["mutant_survival"]["answer_only"]["n"]) == (1, 1)
    assert (sl["mutant_survival_unconditional"]["answer_only"]["k"],
            sl["mutant_survival_unconditional"]["answer_only"]["n"]) == (1, 2)


def test_case_bootstrap_interval_present_and_seeded():
    runs = []
    for i in range(10):
        for t in range(3):
            runs.append(crun("baseline", f"K{i}", t, answer=(i < 5)))
    s = summarize(runs)
    r = s["harness_pass"]["baseline"]["answer_only"]
    assert (r["k"], r["n"]) == (15, 30)
    low, high = r["ci95_case"]
    # clustered by case (all 3 trials of a case agree), so the by-case interval is wider than Wilson
    assert low < r["ci95"][0] and high > r["ci95"][1]
    assert 0.0 <= low <= 0.5 <= high <= 1.0
    assert summarize(runs)["harness_pass"]["baseline"]["answer_only"]["ci95_case"] == [low, high]


def test_case_bootstrap_degenerate():
    from evals.report import case_rate
    assert case_rate([])["ci95_case"] == [0.0, 0.0]
    assert case_rate([("a", True), ("b", True)])["ci95_case"] == [1.0, 1.0]


def test_per_slice_brittle_fail():
    runs = [
        crun("alt_recheck", "S1", 0, slice_="happy",
             modes={"strict": False, "unordered": True, "subset": True, "superset": True}),
        crun("alt_recheck", "S2", 0, slice_="happy"),
        crun("alt_recheck", "S3", 0, slice_="injection"),
        crun("alt_recheck", "S4", 0, slice_="injection", answer=False),  # not eligible
    ]
    s = summarize(runs)
    bf = s["slices"]["happy"]["brittle_fail"]["alt_recheck"]
    assert (bf["strict"]["k"], bf["strict"]["n"]) == (1, 2)
    assert bf["constraints"]["k"] == 0
    assert s["slices"]["injection"]["brittle_fail"]["alt_recheck"]["strict"]["n"] == 1


def test_render_markdown_shows_both_intervals_and_tables():
    from evals.report import render_markdown
    runs = [
        crun("baseline", "P1", 0),
        crun("A", "P1", 0, cons=False, fired=FIRED_A),
        crun("alt_recheck", "P1", 0),
    ]
    md = render_markdown(summarize(runs), {})
    assert "per-run" in md and "by case" in md
    assert "conditioned on baseline" in md.lower()
    assert "unconditional" in md.lower()
    assert "Brittle-fail rate by slice" in md
