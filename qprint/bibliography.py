"""Import hints derived from rendered bibliography entries; no network lookups."""
from html.parser import HTMLParser
import re
from urllib.parse import unquote, urlparse


_ARXIV_ID = r'(?:\d{4}\.\d{4,5}|[a-zA-Z][\w.-]*/\d{7})(?:v[1-9]\d*)?'


class _ReferenceText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.links = [], []

    def handle_data(self, data):
        self.text.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {'p', 'br', 'div', 'li'}:
            self.text.append(' ')
        if tag == 'a':
            self.links.extend(value for key, value in attrs if key == 'href' and value)


def reference_arxiv_id(html: str) -> str | None:
    """Require an explicit arXiv marker or an arXiv URL, never a guessed title."""
    parser = _ReferenceText()
    parser.feed(html)
    text = ''.join(parser.text)
    candidates = []
    for match in re.finditer(r'\barxiv\s*:\s*(' + _ARXIV_ID + r')(?![\w/]|\.\d)', text, re.I):
        candidates.append(match[1])
    urls = parser.links + re.findall(r'https?://[^\s<>"\']+', text)
    for value in urls:
        try:
            url = urlparse(value)
            path = unquote(url.path).rstrip('.,;)')
            if url.hostname in {'arxiv.org', 'www.arxiv.org', 'export.arxiv.org'}:
                identifier = re.sub(r'^/(?:abs|pdf|src|e-print)/', '', path).removesuffix('.pdf')
            elif url.hostname in {'doi.org', 'dx.doi.org'} and path.lower().startswith('/10.48550/arxiv.'):
                identifier = path[len('/10.48550/arxiv.'):]
            else:
                continue
            if re.fullmatch(_ARXIV_ID, identifier):
                candidates.append(identifier)
        except ValueError:
            continue
    # A reference that mentions different papers must not silently import one.
    identities = {re.sub(r'v[1-9]\d*$', '', value).lower() for value in candidates}
    return candidates[0] if len(identities) == 1 else None
