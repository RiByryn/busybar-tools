"""Unit tests for run_fetch with local sources (no network/device)."""
import os
import types

import busybar_tools as bt


def _args(**kw):
    base = dict(target=22, signed=True, update_bundle_type="update", unpack=False, output=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_local_file_no_output_prints_cache_path(tmp_path, capsys):
    f = tmp_path / "x.tgz"
    f.write_text("x")
    ret = bt.run_fetch(_args(source=str(f)))
    out = capsys.readouterr().out.strip()
    assert ret == 0
    assert out == str(f)


def test_local_file_copied_to_output_dir(tmp_path):
    f = tmp_path / "x.tgz"
    f.write_text("x")
    outdir = tmp_path / "o"
    ret = bt.run_fetch(_args(source=str(f), output=str(outdir) + os.sep))
    assert ret == 0
    assert os.path.isfile(outdir / "x.tgz")


def test_local_dir_source_with_unpack_returns_dir(tmp_path, capsys):
    d = tmp_path / "unpacked"
    d.mkdir()
    (d / "f").write_text("y")
    ret = bt.run_fetch(_args(source=str(d), unpack=True))
    out = capsys.readouterr().out.strip()
    assert ret == 0
    assert out == str(d)
