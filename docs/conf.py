import importlib.metadata
import re

project = "mkpkg"
author = "Julian Berman"
copyright = f"2019, {author}"

release = importlib.metadata.version("mkpkg")
version, _, _ = release.rpartition(".")

language = "en"
default_role = "any"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.spelling",
    "sphinxext.opengraph",
]

pygments_style = "lovelace"
pygments_dark_style = "one-dark"

html_theme = "furo"


def entire_domain(host):
    return r"http.?://" + re.escape(host) + r"($|/.*)"


linkcheck_ignore = [
    entire_domain("img.shields.io"),
    "https://github.com/Julian/mkpkg/actions",
    "https://github.com/Julian/mkpkg/workflows/CI/badge.svg",
]

# = Extensions =

# -- autosectionlabel --

autosectionlabel_prefix_document = True

# -- sphinxcontrib-spelling --

spelling_word_list_filename = "spelling-wordlist.txt"
spelling_show_suggestions = True
