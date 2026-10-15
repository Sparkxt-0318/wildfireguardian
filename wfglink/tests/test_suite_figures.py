from wfglink.viz.suite_figures import _missing_reason, case_errors_figure


def test_missing_reason_names_declined_exposure():
    assert _missing_reason({"exposure_ok": 0.0}, "exposure_rel_err") == "declined"
    assert _missing_reason({"exposure_ok": 1.0}, "exposure_rel_err") == "n/a"
    assert _missing_reason({}, "track_speed_med_rel_err") == "no tracks"
    assert _missing_reason({}, "cpc_gross_rel_err") == "n/a"


def test_case_errors_figure_writes_png_and_svg(tmp_path):
    summary = {
        "base": {"track_speed_med_rel_err": 0.02, "cpc_gross_rel_err": -0.7, "exposure_rel_err": None, "exposure_ok": 0.0},
        "dark": {"track_speed_med_rel_err": None, "cpc_gross_rel_err": -1.0, "exposure_rel_err": 0.05, "exposure_ok": 1.0},
    }
    out = case_errors_figure(summary, tmp_path / "errors", "test")
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["errors.png", "errors.svg"], (out, names)
