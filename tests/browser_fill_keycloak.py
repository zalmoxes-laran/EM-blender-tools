"""The browser of the sign-in proofs: opens the URL Blender hands it, fills the
dev realm's Keycloak page with a TEST user of the realm (never ORCID), and
photographs the page and the return page Blender's listener answers.

Run by Python's `webbrowser` through `BROWSER` (see blender_shots_sign_in.py):

    BROWSER="<py with playwright> tests/browser_fill_keycloak.py %s"

Env: EM_TEST_USER (default dev), EM_SHOTS (folder for the pictures). Detaches
at once, so the caller is never held while the page is filled.
"""
import os
import subprocess
import sys

if os.environ.get("_EM_FILL_CHILD") != "1":
    env = dict(os.environ, _EM_FILL_CHILD="1")
    subprocess.Popen([sys.executable, __file__, *sys.argv[1:]], env=env,
                     stdout=open(os.path.join(os.environ.get("EM_SHOTS", "/tmp"),
                                              "browser_fill.log"), "a"),
                     stderr=subprocess.STDOUT, start_new_session=True)
    sys.exit(0)

from playwright.sync_api import sync_playwright  # noqa: E402

url = sys.argv[1]
user = os.environ.get("EM_TEST_USER", "dev")
shots = os.environ.get("EM_SHOTS", "/tmp")
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page(viewport={"width": 900, "height": 640})
    page.goto(url)
    page.wait_for_selector("#kc-form-login", timeout=30000)
    page.fill("#username", user)
    page.screenshot(path=os.path.join(shots, "q11_keycloak_page.png"))
    page.fill("#password", user)
    page.click("#kc-login")
    page.wait_for_url("http://127.0.0.1:*/**", timeout=30000)
    page.wait_for_selector("h1", timeout=30000)
    print("RETURN PAGE:", page.inner_text("body"))
    page.screenshot(path=os.path.join(shots, "q11_return_page.png"))
    browser.close()
