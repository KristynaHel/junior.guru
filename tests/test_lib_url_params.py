import pytest

from juniorguru.lib import url_params


@pytest.mark.parametrize(
    "url,param_names,expected",
    [
        ("https://example.com", ["a", "b"], "https://example.com"),
        ("https://example.com?a=1&b=2", ["a", "b"], "https://example.com"),
        ("https://example.com?a=1&c=3&b=2", ["a", "b"], "https://example.com?c=3"),
        ("https://example.com", [], "https://example.com"),
        ("https://example.com?a=1&b=2", [], "https://example.com?a=1&b=2"),
    ],
)
def test_strip_params(url, param_names, expected):
    assert url_params.strip_params(url, param_names) == expected


@pytest.mark.parametrize(
    "url,params,expected",
    [
        ("https://example.com", {"a": 1, "b": 2}, "https://example.com?a=1&b=2"),
        ("https://example.com", {"a": 1, "b": ""}, "https://example.com?a=1&b="),
        ("https://example.com", {"a": 1, "b": None}, "https://example.com?a=1&b="),
        (
            "https://example.com?a=1&b=2",
            {"a": 1, "b": 2},
            "https://example.com?a=1&b=2",
        ),
        (
            "https://example.com?a=1&c=3&b=2",
            {"a": 1, "b": 2},
            "https://example.com?a=1&c=3&b=2",
        ),
        ("https://example.com", {}, "https://example.com"),
        ("https://example.com?a=1&b=2", {}, "https://example.com?a=1&b=2"),
        (
            "https://example.com?a=1&b=2",
            {"a": 1, "b": 42, "c": 2},
            "https://example.com?a=1&b=42&c=2",
        ),
    ],
)
def test_set_params(url, params, expected):
    assert url_params.set_params(url, params) == expected


@pytest.mark.parametrize(
    "url,param_name,expected",
    [
        ("https://example.com", "b", "https://example.com?b=1"),
        ("https://example.com?a=1&b=2&c=3", "b", "https://example.com?a=1&b=3&c=3"),
    ],
)
def test_increment_param(url, param_name, expected):
    assert url_params.increment_param(url, param_name) == expected


@pytest.mark.parametrize(
    "url,param_name,inc,expected",
    [
        ("https://example.com", "b", 25, "https://example.com?b=25"),
        (
            "https://example.com?a=1&b=2&c=3",
            "b",
            25,
            "https://example.com?a=1&b=27&c=3",
        ),
    ],
)
def test_increment_param_inc(url, param_name, inc, expected):
    assert url_params.increment_param(url, param_name, inc) == expected


def test_get_param():
    url = "https://example.com?redirect=https%3A%2F%2Fjobs%2Eexample%2Ecom"

    assert url_params.get_param(url, "redirect") == "https://jobs.example.com"


@pytest.mark.parametrize(
    "url,s,repl,expected",
    [
        ("https://example.com", "alice", "bob", "https://example.com"),
        ("https://alice.example.com", "alice", "bob", "https://alice.example.com"),
        (
            "https://alice.example.com?foo=bar",
            "alice",
            "bob",
            "https://alice.example.com?foo=bar",
        ),
        (
            "https://alice.example.com?foo=bar&moo=alice",
            "alice",
            "bob",
            "https://alice.example.com?foo=bar&moo=bob",
        ),
        (
            "https://alice.example.com?foo=bar&moo=alice&alice=hello",
            "alice",
            "bob",
            "https://alice.example.com?foo=bar&moo=bob&alice=hello",
        ),
    ],
)
def test_replace_in_params(url, s, repl, expected):
    assert url_params.replace_in_params(url, s, repl) == expected


@pytest.mark.parametrize(
    "url,case_insensitive,expected",
    [
        (
            "https://alice.example.com?foo=bar&moo=Alice",
            False,
            "https://alice.example.com?foo=bar&moo=Alice",
        ),
        (
            "https://alice.example.com?foo=bar&moo=ALICE",
            False,
            "https://alice.example.com?foo=bar&moo=ALICE",
        ),
        (
            "https://alice.example.com?foo=bar&moo=Alice",
            True,
            "https://alice.example.com?foo=bar&moo=bob",
        ),
        (
            "https://alice.example.com?foo=bar&moo=ALICE",
            True,
            "https://alice.example.com?foo=bar&moo=bob",
        ),
    ],
)
def test_replace_in_params_case_insensitive(url, case_insensitive, expected):
    assert (
        url_params.replace_in_params(
            url, "alice", "bob", case_insensitive=case_insensitive
        )
        == expected
    )
