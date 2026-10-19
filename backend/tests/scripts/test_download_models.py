"""scripts/download_models.py: direct links, checksums, and never printing the private links."""
import http.server
import importlib.util
import threading
from pathlib import Path
import pytest


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"  # backend/scripts


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dl = _load_script("download_models")


@pytest.mark.parametrize("link", [
    "https://drive.google.com/file/d/1AbC_d-9/view?usp=sharing",
    "https://drive.google.com/open?id=1AbC_d-9",
    "https://drive.google.com/uc?export=download&id=1AbC_d-9",
])
def test_when_given_a_drive_share_link_should_make_it_a_direct_download(link):
    assert dl.direct_url(link) == "https://drive.usercontent.google.com/download?id=1AbC_d-9&export=download&confirm=t"


def test_when_given_another_url_should_leave_it_unchanged():
    assert dl.direct_url("https://example.org/m/best.pt") == "https://example.org/m/best.pt"


def test_when_parsing_model_urls_should_map_file_names_to_links():
    assert dl.parse_urls("best.pt=https://a/x?id=1&y=2, quality_gate.pt=https://b") == {
        "best.pt": "https://a/x?id=1&y=2", "quality_gate.pt": "https://b"}
    with pytest.raises(SystemExit):
        dl.parse_urls("no-equals-sign")


@pytest.fixture
def server(tmp_path):
    (tmp_path / "w.pt").write_bytes(b"weights")
    (tmp_path / "page.html").write_text("<html>sign in</html>")
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(tmp_path), **k)  # noqa: E731
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    handler_log = http.server.SimpleHTTPRequestHandler.log_message
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    http.server.SimpleHTTPRequestHandler.log_message = handler_log


def test_when_downloading_should_verify_the_checksum(server, tmp_path):
    import hashlib

    dest = tmp_path / "out" / "w.pt"
    dest.parent.mkdir()
    dl.download(f"{server}/w.pt", dest, hashlib.sha256(b"weights").hexdigest())
    assert dest.read_bytes() == b"weights"


def test_when_the_checksum_is_wrong_should_save_nothing(server, tmp_path):
    dest = tmp_path / "w2.pt"
    with pytest.raises(dl.DownloadError, match="checksum mismatch"):
        dl.download(f"{server}/w.pt", dest, "0" * 64)
    assert not dest.exists() and not dest.with_suffix(".pt.part").exists()


def test_when_the_link_returns_a_web_page_should_refuse_it(server, tmp_path):
    with pytest.raises(dl.DownloadError, match="web page"):
        dl.download(f"{server}/page.html", tmp_path / "x.pt", "0" * 64)


SECRET_LINK = "https://drive.google.com/file/d/SECRET-DRIVE-ID-123/view?usp=sharing"


def test_when_a_download_fails_should_never_print_the_link(tmp_path, monkeypatch, capsys):
    import sys

    def boom(url, dest, sha):
        raise OSError(f"could not open {url}")  # a library error that echoes the URL

    monkeypatch.setattr(dl, "download", boom)
    monkeypatch.setattr(sys, "argv", ["download_models.py", "--dest", str(tmp_path), "--urls",
                                      f"best.pt={SECRET_LINK},meter_reader.pt=not a url,quality_gate.pt="])
    with pytest.raises(SystemExit) as exit_info:
        dl.main()
    out = capsys.readouterr().out + str(exit_info.value)
    assert "SECRET-DRIVE-ID-123" not in out and "drive.google" not in out and "not a url" not in out
    assert "best.pt: failed (OSError)" in out and "quality_gate.pt: failed (no link" in out
    assert "best.pt, meter_reader.pt, quality_gate.pt" in out  # every file tried, all reported


def test_when_a_model_urls_entry_is_malformed_should_not_echo_it():
    with pytest.raises(SystemExit) as exit_info:
        dl.parse_urls("best.pt=https://a/SECRET-PATH,https://b/SECRET-WITHOUT-EQUALS")
    assert "SECRET" not in str(exit_info.value)


def test_when_model_urls_has_a_stray_link_should_not_echo_it(tmp_path, monkeypatch, capsys):
    import sys

    # A link pasted without "name=" still contains "=" (usp=sharing), so it parses as a bogus name.
    monkeypatch.setattr(sys, "argv", ["download_models.py", "--dest", str(tmp_path), "--urls", SECRET_LINK])
    with pytest.raises(SystemExit) as exit_info:
        dl.main()
    out = capsys.readouterr().out + str(exit_info.value)
    assert "SECRET-DRIVE-ID-123" not in out and "drive.google" not in out
    assert "unknown file name" in out
