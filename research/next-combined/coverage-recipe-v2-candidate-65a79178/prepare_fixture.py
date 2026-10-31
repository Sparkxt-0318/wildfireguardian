from pathlib import Path
p=Path(__file__).parent/'repo/forecast/tests/test_blind_forecast_protocol.py';s=p.read_text()
s=s.replace('''    return module


@pytest.fixture
def freeze_inputs''','''    return _synthetic_recipe_boundary(module)


_SYNTHETIC_RECIPE_VERSIONS = {}


def _synthetic_recipe_boundary(module):
    """Use explicit fixture-local reviewed pins, never auto-admit later mutation."""
    if getattr(module, "_synthetic_recipe_bound", False):
        return module
    real = module._verified_producer_version
    def verify(root, source, phase_id):
        fixture = _SYNTHETIC_RECIPE_VERSIONS.get(str(Path(root).resolve()))
        if fixture is None:
            return real(root, source, phase_id)
        original = module._RECIPE_SOURCE_VERSIONS, module._RECIPE_CURRENT_BASELINE
        module._RECIPE_SOURCE_VERSIONS = {**original[0], **fixture["versions"]}
        module._RECIPE_CURRENT_BASELINE = fixture["current"]
        try:
            return real(root, source, phase_id)
        finally:
            module._RECIPE_SOURCE_VERSIONS, module._RECIPE_CURRENT_BASELINE = original
    module._verified_producer_version = verify
    module._synthetic_recipe_bound = True
    return module


@pytest.fixture
def freeze_inputs''',1)
s=s.replace('''    coverage = fit_coverage_module(freezer)
    root =''','''    coverage = fit_coverage_module(freezer)
    _synthetic_recipe_boundary(freezer.F)
    root =''',1)
s=s.replace('''(evidence / "RUN_PROTOCOL.json").write_text(json.dumps(dict(data_manifest_sha256=coverage.sha(extraction))))''', '''(evidence / "RUN_PROTOCOL.json").write_text(json.dumps(dict(data_manifest_sha256=coverage.sha(extraction),
        split_sha256=coverage.sha(evidence / "SPLIT.json"))))''',1)
s=s.replace('''    source = coverage.producer_sources(root)
    groups, audit_rows''','''    source = coverage.producer_sources(root)
    monkeypatch.setitem(_SYNTHETIC_RECIPE_VERSIONS, str(root.resolve()), dict(current=dict(source),
        versions={coverage.object_sha(source): [phase["phase_id"] for phase in coverage.current_phase_identity()["phases"]]}))
    groups, audit_rows''',1)
s=s.replace('''    source.write_bytes(original + b"\\n# Later metadata-only source comment, never attributed to old runtime.\\n")
    audited''','''    source.write_bytes(original + b"\\n# Later metadata-only source comment, never attributed to old runtime.\\n")
    # This synthetic comment-only current version is explicitly reviewed here;
    # its historical producer remains pinned to the original archived bytes.
    _SYNTHETIC_RECIPE_VERSIONS[str(root.resolve())]["current"]["forecast/wildfire/survival.py"] = module.sha(source)
    audited''',1)
p.write_text(s)
