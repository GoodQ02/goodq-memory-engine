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
        target_scene_id = "186466c96315bb367edd6bc72a96e36cde79291f3de35112379cf11fcd4076ad"
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

def test_retro_sfx_accessibility():
    # Setup report directory
    report_dir = os.path.join("reports", "ui_audit")
    os.makedirs(report_dir, exist_ok=True)
    
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        
        # Capture console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        # Navigate to page
        url = "http://127.0.0.1:30000/ui/retro_console_v1/"
        response = page.goto(url)
        assert response.status == 200, f"Page loaded with status {response.status}"
        
        # Wait for timeline to load scenes
        page.wait_for_selector(".scene-card", timeout=15000)
        
        # 1. Verify Night Mode SFX ON displays CRT/Refresh lines.
        crt_screen = page.locator("#crt-screen")
        assert not crt_screen.evaluate("el => el.classList.contains('no-sfx')")
        
        scanlines = page.locator("#scanlines-layer")
        assert scanlines.evaluate("el => window.getComputedStyle(el).display") != "none"
        
        # 2. Verify Day Mode SFX ON displays CRT/Bezel/Flicker effects.
        theme_btn = page.locator("#toggle-theme")
        # Currently we are on Theme: NIGHT. Click once to change to Theme: DAY.
        theme_btn.click()
        page.wait_for_timeout(200)
        assert "Theme: DAY" in theme_btn.text_content()
        assert page.evaluate("() => document.body.classList.contains('theme-day')")
        
        # Day Mode scanlines/aperture grille effects should be active.
        assert scanlines.evaluate("el => window.getComputedStyle(el).display") != "none"
        
        # Flicker/flutter animation should be active.
        crt_animation = crt_screen.evaluate("el => window.getComputedStyle(el).animationName")
        assert crt_animation and crt_animation != "none"
        
        # 3. Verify SFX OFF applies .no-sfx class to #crt-screen.
        sfx_btn = page.locator("#toggle-sfx")
        sfx_btn.click()
        page.wait_for_timeout(200)
        assert crt_screen.evaluate("el => el.classList.contains('no-sfx')")
        assert "Retro SFX: OFF" in sfx_btn.text_content()
        
        # 4. Verify SFX OFF completely disables text-shadows, box-shadows, animations, and filters on descendant elements
        descendants_styles = page.evaluate("""() => {
            const elements = [
                document.getElementById('crt-screen'),
                document.querySelector('.app-header'),
                document.querySelector('h2'),
                document.querySelector('.scene-card'),
                document.getElementById('toggle-sfx'),
                document.getElementById('search-submit')
            ].filter(Boolean);
            
            return elements.map(el => {
                const style = window.getComputedStyle(el);
                return {
                    tagName: el.tagName,
                    className: el.className,
                    textShadow: style.textShadow,
                    boxShadow: style.boxShadow,
                    animation: style.animation,
                    filter: style.filter
                };
            });
        }""")
        
        for style in descendants_styles:
            assert style["textShadow"] == "none", f"textShadow for {style['className']} is {style['textShadow']}"
            assert style["boxShadow"] == "none", f"boxShadow for {style['className']} is {style['boxShadow']}"
            assert style["filter"] == "none", f"filter for {style['className']} is {style['filter']}"
            assert "none" in style["animation"], f"animation for {style['className']} is {style['animation']}"
            
        # The scanlines should be hidden
        assert scanlines.evaluate("el => window.getComputedStyle(el).display") == "none"
        
        # #crt-screen::after overlay opacity is set to 0.
        after_opacity = page.evaluate("""() => {
            const el = document.getElementById('crt-screen');
            return window.getComputedStyle(el, '::after').opacity;
        }""")
        assert float(after_opacity) == 0.0, f"Opacity of ::after is {after_opacity}"
        
        # 5. Verify theme toggle and Retro SFX toggle remain independent and do not conflict.
        # Transition theme: DAY -> AUTO. SFX is currently OFF.
        theme_btn.click()
        page.wait_for_timeout(200)
        assert "Theme: AUTO" in theme_btn.text_content()
        # SFX should remain OFF
        assert crt_screen.evaluate("el => el.classList.contains('no-sfx')")
        assert "Retro SFX: OFF" in sfx_btn.text_content()
        
        # Now switch SFX ON while theme is AUTO
        sfx_btn.click()
        page.wait_for_timeout(200)
        assert not crt_screen.evaluate("el => el.classList.contains('no-sfx')")
        assert "Retro SFX: ON" in sfx_btn.text_content()
        assert "Theme: AUTO" in theme_btn.text_content()
        
        # 6. Verify no Javascript console errors.
        assert len(console_errors) == 0, f"Console errors detected: {console_errors}"
        
        # 7. Verify that screenshot artifacts are saved locally/privately.
        screenshot_path = os.path.join(report_dir, "screenshot_sfx_off.png")
        page.screenshot(path=screenshot_path)
        assert os.path.exists(screenshot_path)
        
        browser.close()

