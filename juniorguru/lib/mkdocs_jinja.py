from pathlib import Path
from typing import Callable
from jinja2 import Environment, FileSystemLoader

from mkdocs.structure.files import File, Files
from mkdocs.config import Config
from mkdocs.structure.pages import Page
from mkdocs.structure.toc import get_toc
from mkdocs.utils.filters import url_filter

from juniorguru.lib.jinja_cache import BytecodeCache
from juniorguru.lib import loggers, template_filters


CACHE_DIR = Path(".web_cache/jinja")

TEMPLATE_FILTERS = [
    "docs_url",
    "email_link",
    "icon",
    "thousands",
    "sample",
    "remove_p",
    "money_breakdown_ptc",
    "revenue_categories",
    "sample_jobs",
    "assert_empty",
    "relative_url",
    "screenshot_url",
    "absolute_url",
    "mapping",
    "local_time",
    "menu",
    "toc",
    "parent_page",
    "sibling_page",
]


logger = loggers.from_path(__file__)


def monkey_patch() -> None:
    # Monkey patch the File class so that it recognizes .jinja
    # files as documentation pages
    _file_is_documentation_page = File.is_documentation_page
    def is_documentation_page(self: File) -> bool:
        return self.src_uri.endswith('.jinja') or _file_is_documentation_page(self)
    File.is_documentation_page = is_documentation_page

    # Monkey patch the Page class so that it allows skipping Markdown
    # rendering in case the source is .jinja
    _page_render = Page.render
    def render(self, config: Config, files: Files):
        if self.file.src_uri.endswith('.jinja'):
            if self.markdown is None:
                raise RuntimeError("`markdown` field hasn't been set (via `read_source`)")
            self.content = self.markdown
            self.toc = get_toc([])
        else:
            _page_render(self, config, files)
    Page.render = render


def get_macros_dir(config: Config) -> Path:
    return Path(config["docs_dir"]).parent / "macros"


def get_filters() -> dict[str, Callable]:
    return {name: getattr(template_filters, name) for name in TEMPLATE_FILTERS}


def get_env(page: Page, config: Config, files: Files) -> Environment:
    loader = FileSystemLoader(get_macros_dir(config))
    cache = BytecodeCache(CACHE_DIR)
    env = Environment(loader=loader, auto_reload=False, bytecode_cache=cache)
    env.filters.update(get_filters())
    env.filters['url'] = url_filter
    env.filters['md'] = create_md_filter(page, config, files)
    return env


def create_md_filter(page: Page, config: Config, files: Files) -> Callable:
    def md(markdown: str) -> str:
        # Sorcery ahead! So this is a Jinja filter, which takes a Markdown string, e.g. from
        # database, and turns it into HTML markup. One could just 'from markdown import markdown',
        # then call 'markdown(...)' and be done with it, but that wouldn't parse the input in the
        # context of MkDocs Markdown settings. Extensions wouldn't be set the same way. Relative
        # links wouldn't work. For that reason, we want to use the MkDocs' own Markdown rendering.
        #
        # Unfortunately, the Page.render() method isn't really meant to be used anywhere else:
        # https://github.com/mkdocs/mkdocs/blob/79f17b4b71c73460c304e3281f6ff209788a76bf/mkdocs/structure/pages.py#L253
        #
        # The following sorcery works around that bit. It creates an artificial _Page object similar
        # to the real MkDocs' own Page object, but only with the properties used by the Page.render()
        # method. It sets all the configuration, passes the input as the 'markdown' property, and
        # steals the Page.render() method to behave like if it always belonged to the _Page object.
        # Then it calls this new _Page.render() method and returns the 'content' property, to which
        # the method sets the result of the rendering.
        #
        # This works, but is very prone to get broken if MkDocs changes something in their code.
        # In such case one needs to read the new MkDocs code and fix the solution accordingly.
        class _Page:
            def __init__(self):
                self.file = page.file
                self.markdown = markdown
                self.render = page.__class__.render.__get__(self)

        _page = _Page()
        _page.render(config, files)
        return _page.content
    return md