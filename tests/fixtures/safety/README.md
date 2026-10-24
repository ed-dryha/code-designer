# Safety fixtures

Nothing is checked in here on purpose. `tests/test_extract_safety.py` and
`tests/test_discovery_agreement.py` generate their repos (git init, symlinks,
oversized files) in pytest temp dirs at test time.
