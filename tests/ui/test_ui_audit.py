import os
import pytest
from playwright.sync_api import sync_playwright

def test_ui_audit():
    # Setup report directory
    report_dir = os.path.join("reports", "ui_audit")
    os.makedirs(report_dir, exist_ok=True)
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        # Capture console errors and page errors
        console_errors = []
        page_errors = []
        
        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)
                
        def on_pageerror(err):
            page_errors.append(err)
            
        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        
        # Track response status codes
        responses = {}
        def on_response(res):
            responses[res.url] = res.status
        page.on("response", on_response)
        
        # Navigate to page
        url = "http://127.0.0.1:30000/ui/retro_console_v1/"
        response = page.goto(url)
        assert response.status == 200, f"Page loaded with status {response.status}"
        
        # Wait for timeline to load scenes
        page.wait_for_selector(".scene-card", timeout=15000)
        
        # Verify static assets
        for res_url, status in responses.items():
            if "retro.js" in res_url or "retro.css" in res_url:
                assert status == 200, f"Static asset failed to load: {res_url} (status {status})"
                
        # Verify no uncaught exceptions on load
        assert len(page_errors) == 0, f"Uncaught exceptions found: {page_errors}"
        
        # Verify graph canvas is present
        canvas = page.locator("#graph-canvas")
        assert canvas.is_visible(), "Graph canvas is not visible"
        
        # Cycle themes and verify persistence
        theme_btn = page.locator("#toggle-theme")
        
        # Initial: NIGHT
        assert "Theme: NIGHT" in theme_btn.text_content()
        assert page.evaluate("localStorage.getItem('goodq-theme')") == "night"
        
        # Click -> DAY
        theme_btn.click()
        page.wait_for_timeout(200)
        assert "Theme: DAY" in theme_btn.text_content()
        assert page.evaluate("localStorage.getItem('goodq-theme')") == "day"
        
        # Click -> AUTO
        theme_btn.click()
        page.wait_for_timeout(200)
        assert "Theme: AUTO" in theme_btn.text_content()
        assert page.evaluate("localStorage.getItem('goodq-theme')") == "auto"
        
        # Click -> NIGHT
        theme_btn.click()
        page.wait_for_timeout(200)
        assert "Theme: NIGHT" in theme_btn.text_content()
        assert page.evaluate("localStorage.getItem('goodq-theme')") == "night"
        
        # Select scene card with arbitration data and click Logs tab
        target_scene_id = "91b081ff8e217a307f50fb8377add00ac55779975fb89e4d7e25927cf629c94f"
        scene_card = page.locator(f'[data-scene-id="{target_scene_id}"]')
        assert scene_card.is_visible(), f"Scene card {target_scene_id} not found"
        scene_card.click()
        page.wait_for_timeout(500)
        
        # Click Logs tab in inspector
        logs_tab = page.locator("#inspect-tab-logs")
        assert logs_tab.is_visible()
        logs_tab.click()
        page.wait_for_timeout(500)
        
        # Check Cognitive Arbitration starts visible
        cog_toggle = page.locator(".cognitive-section .disag-toggle-btn")
        cog_body = page.locator(".cognitive-body")
        assert cog_toggle.is_visible()
        assert "Hide" in cog_toggle.text_content()
        assert cog_body.is_visible()
        
        # Toggle: click Hide -> body hidden
        cog_toggle.click()
        page.wait_for_timeout(200)
        assert not cog_body.is_visible()
        assert "Show" in cog_toggle.text_content()
        
        # Toggle: click Show -> body visible
        cog_toggle.click()
        page.wait_for_timeout(200)
        assert cog_body.is_visible()
        assert "Hide" in cog_toggle.text_content()
        
        # Run search query "record"
        query_input = page.locator("#query-input")
        query_input.fill("record")
        page.locator("#search-submit").click()
        
        # Wait for timeline grid to have matched results
        page.wait_for_selector(".scene-card.matched", timeout=10000)
        matched_cards = page.locator(".scene-card.matched")
        assert matched_cards.count() > 0, "No matched scenes found for query 'record'"
        
        # Inject privacy redact styles before taking screenshots
        page.add_style_tag(content="""
            .scene-frame img, .inspector-keyframe-img, .scene-card-summary, .scene-card-id,
            .details-title, .details-subtitle, .details-summary, .visual-caption-block,
            .ocr-text-block, .transcript-text, .transcript-speaker {
                filter: blur(15px) !important;
            }
        """)
        
        # Screenshot for NIGHT theme (Currently it is NIGHT)
        page.wait_for_timeout(200)
        page.screenshot(path=os.path.join(report_dir, "screenshot_night.png"))
        
        # Screenshot for DAY theme (Click once NIGHT -> DAY)
        theme_btn.click()
        page.wait_for_timeout(200)
        page.screenshot(path=os.path.join(report_dir, "screenshot_day.png"))
        
        # Screenshot for AUTO theme (Click again DAY -> AUTO)
        theme_btn.click()
        page.wait_for_timeout(200)
        page.screenshot(path=os.path.join(report_dir, "screenshot_auto.png"))
        
        browser.close()
        print("UI audit Playwright tests passed successfully!")

def test_stitching_workbench_load():
    # Setup report directory
    report_dir = os.path.join("reports", "ui_audit")
    os.makedirs(report_dir, exist_ok=True)
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        # Capture console errors and page errors
        console_errors = []
        page_errors = []
        
        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)
                
        def on_pageerror(err):
            page_errors.append(err)
            
        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        
        # Navigate to page
        url = "http://127.0.0.1:30000/ui/stitching_workbench/"
        response = page.goto(url)
        assert response.status == 200, f"Stitching Workbench loaded with status {response.status}"
        
        # Wait for system status to be online
        page.wait_for_function("document.getElementById('system-status').textContent.includes('ONLINE')", timeout=10000)
        
        # Verify page elements
        status_text = page.locator("#system-status").text_content()
        assert "ONLINE" in status_text, f"System status did not become ONLINE, got: {status_text}"
        assert page.locator(".mutation-warning-banner").is_visible(), "Mutation warning banner not visible"
        assert page.locator("#unstitched-list").is_visible(), "Unstitched list panel not visible"
        assert page.locator("#mappings-list").is_visible(), "Mappings ledger panel not visible"
        
        # Inject privacy redact styles before taking screenshots
        page.add_style_tag(content="""
            .pattern-title, .pattern-excerpt, .mapping-source, .mapping-target,
            .mapping-note, #selected-pattern-name, #selected-pattern-transcript {
                filter: blur(15px) !important;
            }
        """)
        
        # Screenshot of stitching workbench
        page.screenshot(path=os.path.join(report_dir, "screenshot_stitching.png"))
        
        # Verify no uncaught exceptions on load
        assert len(page_errors) == 0, f"Uncaught exceptions found: {page_errors}"
        browser.close()
        print("Stitching Workbench Playwright tests passed successfully!")
