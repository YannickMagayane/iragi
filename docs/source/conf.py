# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Ensure iragi is accessible to Sphinx autodoc
sys.path.insert(0, os.path.abspath("../.."))
sys.path.insert(0, os.path.abspath("../../iragi"))

import iragi

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Iragi"
copyright = "2026, Yannick Magayane"
author = "Yannick Magayane"
release = getattr(iragi, "__version__", "0.2.0")
version = release

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "myst_parser",
]

# Add django extension if django is configured
try:
    import django
    import sphinxcontrib_django
    # Optional django settings configuration if needed in the future
except ImportError:
    pass

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
myst_heading_anchors = 3
myst_enable_extensions = ["colon_fence", "deflist"]


# Napoleon settings for parsing docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_title = f"Iragi {release} Documentation"

# GitHub integration for RTD theme
html_context = {
    "display_github": True,
    "github_user": "YannickMagayane",
    "github_repo": "iragi",
    "github_version": "main",
    "conf_py_path": "/docs/source/",
}

html_theme_options = {
    "display_version": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": True,
    "vcs_pageview_mode": "blob",
}
