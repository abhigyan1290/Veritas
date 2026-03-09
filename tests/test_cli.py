import pytest
from unittest.mock import patch, MagicMock
from argparse import Namespace
from veritas.cli import _format_money, _render_table, run_diff, run_stats

def test_format_money():
    assert _format_money(0.1234567) == "$0.123457"
    assert _format_money(1.5) == "$1.500000"
    assert _format_money(0) == "$0.000000"

def test_render_table_empty():
    assert _render_table(["H1", "H2"], []) == "No data."

def test_render_table_data():
    headers = ["Name", "Cost"]
    rows = [["TestA", "$1.00"], ["TestB", "$2.50"]]
    
    out = _render_table(headers, rows)
    assert "-----" in out
    assert "Name" in out
    assert "Cost" in out
    assert "TestA" in out

@patch("veritas.cli.compare_commits")
@patch("veritas.cli.SQLiteSink")
def test_run_diff_success(mock_sink_cls, mock_compare, capsys):
    mock_sink = MagicMock()
    mock_sink_cls.return_value = mock_sink

    # Mock the return values from the engine
    mock_compare.return_value = {
        "commit_a_stats": {"count": 1, "avg_cost_usd": 1.0, "avg_tokens_in": 100, "avg_tokens_out": 50},
        "commit_b_stats": {"count": 1, "avg_cost_usd": 1.0, "avg_tokens_in": 100, "avg_tokens_out": 50},
        "delta_cost_usd": 0.0,
        "percent_change": 0.0,
        "is_regression": False,
    }

    args = Namespace(feature="test_feat", commit_a="abc", commit_b="def", command="diff")
    
    with pytest.raises(SystemExit) as e:
        run_diff(args)

    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "Comparing feature 'test_feat'" in captured.out
    assert "✅ OK: No significant cost regression detected." in captured.out

@patch("veritas.cli.compare_commits")
@patch("veritas.cli.SQLiteSink")
def test_run_diff_regression(mock_sink_cls, mock_compare, capsys):
    mock_sink = MagicMock()
    mock_sink_cls.return_value = mock_sink

    # Simulate an expensive regression
    mock_compare.return_value = {
        "commit_a_stats": {"count": 1, "avg_cost_usd": 1.0, "avg_tokens_in": 100, "avg_tokens_out": 50},
        "commit_b_stats": {"count": 1, "avg_cost_usd": 50.0, "avg_tokens_in": 5000, "avg_tokens_out": 2500},
        "delta_cost_usd": 49.0,
        "percent_change": 49.0,
        "is_regression": True,
    }

    args = Namespace(feature="test_feat", commit_a="abc", commit_b="def", command="diff")
    
    with pytest.raises(SystemExit) as e:
        run_diff(args)

    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "❌ REGRESSION DETECTED" in captured.out
