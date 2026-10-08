from __future__ import annotations

from ledgersense import cli


def test_demo_runs(capsys):
    cli.demo()
    out = capsys.readouterr().out
    assert "LedgerSense demo" in out
    assert "Trial balance" in out
    assert "net income" in out
    # The injected outlier must be reported.
    assert "anomal" in out.lower()
    # Tamper-evidence section shows a broken then restored chain.
    assert "after editing entry" in out


def test_main_usage(capsys):
    assert cli.main() == 1
    assert "usage" in capsys.readouterr().out
