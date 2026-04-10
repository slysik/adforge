"""Tests for sidebar navigation structure, data, and CSS."""

from __future__ import annotations

import importlib
import re
import sys
import types
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers — import app module without actually running Streamlit
# ---------------------------------------------------------------------------

def _load_app_source() -> str:
    """Return the raw source of src/app.py."""
    from pathlib import Path

    return (Path(__file__).resolve().parent.parent / "src" / "app.py").read_text()


def _extract_custom_css(source: str) -> str:
    """Pull the CUSTOM_CSS triple-quoted string from the source."""
    # The variable is assigned as: CUSTOM_CSS = \"\"\"...\"\"\"
    match = re.search(r'CUSTOM_CSS\s*=\s*"""(.*?)"""', source, re.DOTALL)
    assert match, "Could not find CUSTOM_CSS in app.py"
    return match.group(1)


def _import_app_nav_items():
    """Import just NAV_ITEMS from app.py by mocking streamlit."""
    source = _load_app_source()

    # We need to extract NAV_ITEMS without running the whole Streamlit app.
    # Parse the NAV_ITEMS definition from source.
    match = re.search(
        r"^(NAV_ITEMS:\s*list\[dict\]\s*=\s*\[.*?^\])",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert match, "Could not find NAV_ITEMS in app.py"
    nav_items_code = match.group(1)

    local_ns: dict = {}
    exec(nav_items_code, {}, local_ns)  # noqa: S102
    return local_ns["NAV_ITEMS"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNavPageDefault:
    """Verify the default nav_page session state value."""

    def test_default_nav_page_is_brief(self):
        source = _load_app_source()
        # The app sets: if "nav_page" not in st.session_state: st.session_state.nav_page = "brief"
        assert 'st.session_state.nav_page = "brief"' in source

    def test_nav_page_init_is_guarded(self):
        source = _load_app_source()
        assert '"nav_page" not in st.session_state' in source


class TestNavItems:
    """Verify the NAV_ITEMS data structure."""

    @pytest.fixture()
    def nav_items(self):
        return _import_app_nav_items()

    def test_nav_items_is_list(self, nav_items):
        assert isinstance(nav_items, list)

    def test_nav_items_has_sections(self, nav_items):
        sections = [s["section"] for s in nav_items]
        assert "Create" in sections
        assert "Pipeline" in sections
        assert "Tools" in sections

    def test_all_expected_pages_present(self, nav_items):
        pages = set()
        for section in nav_items:
            for item in section["items"]:
                pages.add(item["page"])
        assert pages == {"brief", "results", "analytics", "assets"}

    def test_each_item_has_required_keys(self, nav_items):
        required = {"page", "btn_key"}
        for section in nav_items:
            assert "section" in section
            assert "items" in section
            for item in section["items"]:
                assert required.issubset(item.keys()), f"Missing keys in {item}"

    def test_brief_item_details(self, nav_items):
        brief_items = [
            item
            for section in nav_items
            for item in section["items"]
            if item["page"] == "brief"
        ]
        assert len(brief_items) == 1
        assert brief_items[0]["icon"] == "📝"

    def test_results_item_is_dynamic(self, nav_items):
        results_items = [
            item
            for section in nav_items
            for item in section["items"]
            if item["page"] == "results"
        ]
        assert len(results_items) == 1
        assert results_items[0].get("dynamic") is True

    def test_analytics_item_exists(self, nav_items):
        analytics = [
            item
            for section in nav_items
            for item in section["items"]
            if item["page"] == "analytics"
        ]
        assert len(analytics) == 1
        assert analytics[0]["icon"] == "📊"

    def test_assets_item_exists(self, nav_items):
        assets = [
            item
            for section in nav_items
            for item in section["items"]
            if item["page"] == "assets"
        ]
        assert len(assets) == 1
        assert assets[0]["icon"] == "📁"


class TestCustomCSS:
    """Verify sidebar CSS classes are defined."""

    @pytest.fixture()
    def css(self):
        return _extract_custom_css(_load_app_source())

    def test_nav_section_class_defined(self, css):
        assert ".af-nav-section" in css

    def test_nav_section_has_uppercase(self, css):
        # The section header should be uppercase
        assert "text-transform: uppercase" in css

    def test_nav_item_class_defined(self, css):
        assert ".af-nav-item" in css

    def test_nav_icon_class_defined(self, css):
        assert ".af-nav-icon" in css

    def test_nav_label_class_defined(self, css):
        assert ".af-nav-label" in css

    def test_nav_divider_class_defined(self, css):
        assert ".af-nav-divider" in css


class TestPageHandlers:
    """Verify that all nav pages have corresponding handler blocks."""

    @pytest.fixture()
    def source(self):
        return _load_app_source()

    def test_brief_page_handler(self, source):
        assert 'nav_page == "brief"' in source

    def test_results_page_handler(self, source):
        assert 'nav_page == "results"' in source

    def test_analytics_page_handler(self, source):
        assert 'nav_page == "analytics"' in source

    def test_assets_page_handler(self, source):
        assert 'nav_page == "assets"' in source


class TestRenderSidebarNav:
    """Verify that _render_sidebar_nav is defined and callable."""

    def test_render_function_defined(self):
        source = _load_app_source()
        assert "def _render_sidebar_nav()" in source

    def test_render_function_renders_sections(self):
        """Verify the function renders section labels from NAV_ITEMS."""
        source = _load_app_source()
        nav_items = _import_app_nav_items()
        for section in nav_items:
            # Each section label should appear in the render function body
            assert section["section"] in source
