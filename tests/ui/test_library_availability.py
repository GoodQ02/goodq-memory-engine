"""Isolated browser witnesses; no live services or saved media."""
from pathlib import Path
from urllib.parse import urlsplit, unquote

import pytest

from tests.unit.test_combined_library import library


@pytest.fixture
def library_page(library):
    """Real UI assets + production middleware, with every browser request intercepted.

    No listening test service, real API, models or saved corpus is used.
    """
    import mimetypes
    from playwright.sync_api import sync_playwright

    client, _, behavior = library
    root = Path(__file__).resolve().parents[2]
    seen = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_navigation_timeout(8000)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def handle(route):
            request = route.request
            url = urlsplit(request.url)
            if url.hostname != "goodq.test":
                route.abort()
                return
            seen.append((request.method, url.path, url.query))
            if url.path.startswith("/ui/"):
                path = (root / unquote(url.path).lstrip("/")).resolve()
                if path.is_dir():
                    path /= "index.html"
                assert path.is_relative_to(root / "ui")
                route.fulfill(body=path.read_bytes(), content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream")
            elif url.path in {"/api/system/videos", "/api/identity/appearances/saved"} or url.path.endswith("/scenes"):
                response = client.request(request.method, url.path + ("?" + url.query if url.query else ""))
                route.fulfill(status=response.status_code, body=response.content,
                              headers={k: v for k, v in response.headers.items() if k != "content-length"})
            else:
                assert request.method == "GET", "Unexpected UI mutation"
                route.fulfill(json={})

        page.route("**/*", handle)
        try:
            yield page, seen, behavior, errors
        finally:
            browser.close()


@pytest.mark.parametrize("view", ["retro_console_v1/", "identity_workbench/?tab=appearances"])
def test_real_ui_keeps_local_browsing_and_marks_partial_library(library_page, view):
    from playwright.sync_api import expect

    page, seen, behavior, errors = library_page
    behavior["offline"] = True
    page.goto("http://goodq.test/ui/" + view)
    notice = page.locator("#library-availability")
    expect(notice).to_be_visible()
    expect(notice).to_contain_text("Movie two unavailable")
    expect(notice).to_contain_text("totals are incomplete")
    if view.startswith("retro"):
        expect(page.locator("#dataset-select")).to_have_value("One")
        expect(page.locator(".scene-card")).to_have_count(1)
        expect(page.locator(".scene-card")).to_contain_text("Local saved scene")
        assert page.evaluate("GoodQLibrary.caption").startswith("1 available")
    else:
        expect(page.locator("#saved-people-status")).to_contain_text("1 saved appearance links")
        expect(page.locator("#collection-source-select option[value=two]")).to_have_js_property("disabled", True)
    assert not errors
    assert all(method == "GET" for method, _, _ in seen)


def test_real_ui_explicit_offline_source_never_opens_local_movie(library_page):
    from playwright.sync_api import expect

    page, seen, behavior, errors = library_page
    behavior["offline"] = True
    page.goto("http://goodq.test/ui/retro_console_v1/?library_source=two")
    expect(page.locator("#library-availability")).to_be_visible()
    expect(page.locator("#dataset-select")).to_have_value("")
    assert not any(path == "/api/videos/One/scenes" for _, path, _ in seen)
    assert page.evaluate("GoodQLibrary.source") == "two"
    page.select_option("#dataset-select", "One")
    expect(page.locator(".scene-card")).to_have_count(1)
    assert page.evaluate("GoodQLibrary.source") == "local"
    assert not errors


def test_real_ui_recovery_on_reload_clears_unavailable_state(library_page):
    from playwright.sync_api import expect

    page, _, behavior, errors = library_page
    behavior["offline"] = True
    page.goto("http://goodq.test/ui/identity_workbench/?tab=appearances")
    expect(page.locator("#library-availability")).to_be_visible()
    behavior["offline"] = False
    page.reload()
    expect(page.locator("#collection-source-select option[value=two]")).to_have_js_property("disabled", False)
    expect(page.locator("#saved-people-status")).to_contain_text("2 saved appearance links")
    expect(page.locator("#library-availability")).not_to_be_visible()
    assert not errors
