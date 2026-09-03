from __future__ import annotations

from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return " ".join(part.strip() for part in self._parts if part.strip())


def strip_html(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if "<" not in stripped and ">" not in stripped:
        return stripped
    parser = _TextExtractor()
    parser.feed(stripped)
    parser.close()
    text = parser.text()
    return text or None
