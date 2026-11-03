"""Recognize only the enrichment prefix produced by our chunk splitter."""
import re

_SUMMARY = re.compile(r"\A\[AI Shrnutí(?: \(Klikněte na 'Znovu vygenerovat' pro AI zpracování\))?: .*?\]\r?\n\r?\n", re.DOTALL)


def without_ai_summary(content: str) -> str:
    return _SUMMARY.sub("", content, count=1)
