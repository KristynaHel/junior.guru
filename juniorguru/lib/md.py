import re

from markdown import markdown
from markdown.extensions.toc import TocExtension


LINK_RE = re.compile(r'''
    \!?
    \[
        ([^\]]+)
    \]
    \(
        [^\)]+
    \)
''', re.VERBOSE)

URL_RE = re.compile(r'''
    https?://(www\.)?
''', re.VERBOSE)


def md(markdown_text):
    return markdown(markdown_text,
                    output_format='html5',
                    extensions=[TocExtension(marker='', baselevel=1)])


def strip_links(markdown_text):
    return LINK_RE.sub(r'\1', markdown_text)


def neutralize_urls(markdown_text):
    return URL_RE.sub('', markdown_text)
