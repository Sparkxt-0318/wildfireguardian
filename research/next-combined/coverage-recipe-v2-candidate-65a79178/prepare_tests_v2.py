from pathlib import Path
p=Path(__file__).parent/'repo/forecast/tests/test_source_recipe_compatibility.py';s=p.read_text()
s=s.replace('''@pytest.mark.parametrize("variant", ["base", "mixed_base"])''','''@pytest.mark.parametrize("variant", ["d4_wind", "mixed_base"])''',1)
s=s.replace('''    historical = check(recipe, without_custody(current), variant)''','''    historical = check(recipe, F._source_blob(F.REPO, "research/forecast-v2/scripts/pipeline.py",
        "80a806e1177592fc4c16c12e78090a942b5cd1d985e644513fa8f401b8cf0439"), variant)''',1)
a=s.index('def old_utc_and_key(source):');b=s.index('\n\ndef test_real_unfloored',a)
s=s[:a]+'''def old_utc_and_key(source):
    F = module()
    return F._source_blob(F.REPO, "research/forecast-v2/scripts/pipeline.py",
        "fe2304501159aa7340f305e8eb7a93e4199c59f9bb100f30667f60daeec00978")
'''+s[b:]
s=s.replace('match="consumed input recipe differs: fit_samples"','match="whole-pipeline source version"')
s=s.replace('match="consumed input recipe differs: kriged_samples"','match="whole-pipeline source version"')
s=s.replace('match="consumed input recipe differs"','match="whole-pipeline source version"')
s=s.replace('match="unconsumed definition header differs: kriged_samples"','match="whole-pipeline source version"')
s=s.replace('''    proof = check(recipe, without_custody(current), "base")''','''    proof = check(recipe, old_utc_and_key(current), "base")''',1)
p.write_text(s)
