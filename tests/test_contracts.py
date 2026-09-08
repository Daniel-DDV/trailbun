import copy

import pytest

from trailbun import contracts


def test_contract_defaults_and_digest_are_deterministic(contract):
    result = contracts.validate(contract)
    assert result["checks"][0]["timeout_seconds"] == 60
    assert result["expected_red"] == []
    assert contracts.digest(result) == contracts.digest(contracts.validate(contract))
    assert "timeout_seconds" not in contract["checks"][0]


@pytest.mark.parametrize("path", ["../src", "src/../secret", ".git/config", ".trailbun/state.json", "src/*", "C:/outside", "/outside", ""])
def test_contract_rejects_ambiguous_or_outside_scopes(contract, path):
    contract["allowed_paths"] = [path]
    with pytest.raises(ValueError):
        contracts.validate(contract)


@pytest.mark.parametrize("timeout", [0, -1, 601, True, "60"])
def test_contract_rejects_unbounded_check_timeouts(contract, timeout):
    contract["checks"][0]["timeout_seconds"] = timeout
    with pytest.raises(ValueError):
        contracts.validate(contract)


def test_contract_rejects_duplicate_checks_and_unknown_expected_red(contract):
    contract["checks"].append(copy.deepcopy(contract["checks"][0]))
    with pytest.raises(ValueError):
        contracts.validate(contract)
    contract["checks"].pop()
    contract["expected_red"] = ["unknown"]
    with pytest.raises(ValueError):
        contracts.validate(contract)


def test_literal_bracket_route_paths_are_not_glob_patterns(contract):
    contract["allowed_paths"] = ["app/[slug]/page.tsx"]
    assert contracts.validate(contract)["allowed_paths"] == ["app/[slug]/page.tsx"]
