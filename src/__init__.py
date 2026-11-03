"""Shorts Factory. All text files are UTF-8, whatever the OS default is (Windows uses cp1252, which cannot read the UI
or any non-English script, and made the page return "Internal Server Error")."""
import pathlib

_read, _write = pathlib.Path.read_text, pathlib.Path.write_text


def _read_text(self, encoding=None, errors=None):
    return _read(self, encoding or "utf-8", errors)


def _write_text(self, data, encoding=None, errors=None, newline=None):
    return _write(self, data, encoding or "utf-8", errors, newline) if newline is not None else _write(self, data, encoding or "utf-8", errors)


pathlib.Path.read_text, pathlib.Path.write_text = _read_text, _write_text
