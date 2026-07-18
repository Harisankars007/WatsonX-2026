"""
Phase 1: Bot joins Google Meet as a participant using Selenium.
Uses Selenium Manager (built-in) — no separate ChromeDriver needed.
"""

import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import MEET_URL, BOT_DISPLAY_NAME, BOT_EMAIL, BOT_PASSWORD

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("MeetBot.Join")


def get_driver():
    """Set up Chrome with required flags for audio capture.
    Uses Selenium Manager (built-in since Selenium 4.6) — no ChromeDriver install needed."""
    options = Options()

    # Allow microphone and camera without prompts
    options.add_argument("--use-fake-ui-for-media-stream")
    options.add_argument("--use-fake-device-for-media-stream")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-infobars")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    options.add_argument("--lang=en-US")

    # Suppress "Chrome is being controlled by automated software" banner
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Allow capturing audio from tab
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.media_stream_mic": 1,
        "profile.default_content_setting_values.media_stream_camera": 1,
        "profile.default_content_setting_values.notifications": 2,
    })

    driver = webdriver.Chrome(options=options)
    return driver


def login_google(driver):
    """Log in to Google account for the bot."""
    log.info("Logging in to Google account...")
    driver.get("https://accounts.google.com/signin")

    wait = WebDriverWait(driver, 20)

    # Enter email
    email_field = wait.until(EC.presence_of_element_located((By.ID, "identifierId")))
    email_field.send_keys(BOT_EMAIL)
    driver.find_element(By.ID, "identifierNext").click()

    time.sleep(2)

    # Enter password
    password_field = wait.until(EC.presence_of_element_located((By.NAME, "Passwd")))
    password_field.send_keys(BOT_PASSWORD)
    driver.find_element(By.ID, "passwordNext").click()

    time.sleep(3)
    log.info("Google login complete.")


def join_meeting(driver, meet_url=MEET_URL):
    """Navigate to Meet URL and join the meeting."""
    log.info(f"Navigating to Meet: {meet_url}")
    driver.get(meet_url)

    wait = WebDriverWait(driver, 40)

    # Wait for page to fully load
    time.sleep(6)

    # ── Dismiss "Got it" / cookie / consent banners ──
    for selector in [
        "//button[contains(text(),'Got it')]",
        "//button[contains(text(),'Accept all')]",
        "//button[contains(text(),'Reject all')]",
        "//button[@aria-label='Dismiss']",
    ]:
        try:
            btn = driver.find_element(By.XPATH, selector)
            btn.click()
            time.sleep(1)
        except NoSuchElementException:
            pass

    time.sleep(2)

    # ── Turn off mic & camera before joining ──
    for label in [
        "Turn off microphone",
        "Microphone",
        "Turn off camera",
        "Camera",
    ]:
        _click_if_present(driver, f"//button[@aria-label='{label}']")
    time.sleep(1)

    # ── Set display name (guest join) ──
    try:
        name_field = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='Your name']")
        ))
        name_field.clear()
        name_field.send_keys(BOT_DISPLAY_NAME)
        log.info(f"Display name set to: {BOT_DISPLAY_NAME}")
        time.sleep(1)
    except TimeoutException:
        log.info("Name field not found — likely signed in already.")

    # ── Click Join / Ask to join — expanded selector list ──
    join_buttons = [
        # Text-based
        "//button[.//span[contains(text(),'Join now')]]",
        "//button[.//span[contains(text(),'Ask to join')]]",
        "//button[.//span[contains(text(),'Join')]]",
        # aria-label based
        "//button[@aria-label='Join now']",
        "//button[@aria-label='Ask to join']",
        "//button[@aria-label='Join call']",
        # data attribute
        "//button[contains(@data-idom-class,'join')]",
        # jsname based (Google Meet uses jsname attributes)
        "//button[@jsname='Qx7uuf']",
        "//button[@jsname='CQylAd']",
        # Any button containing join text (case insensitive)
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'join')]",
    ]

    joined = False
    for xpath in join_buttons:
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            btn.click()
            joined = True
            log.info(f"✅ Joined using selector: {xpath}")
            break
        except TimeoutException:
            continue

    if not joined:
        # Check if already in the meeting (no lobby — direct join happened)
        try:
            already_in = driver.find_elements(By.XPATH,
                "//button[@aria-label='Turn off microphone'] | //button[@aria-label='Leave call']"
            )
            if already_in:
                log.info("✅ Already in the meeting (direct join — no lobby)!")
                return True
        except Exception:
            pass

        # Take screenshot for debugging
        try:
            driver.save_screenshot("join_failed.png")
            log.error("❌ Could not find Join button. Screenshot saved: join_failed.png")
        except Exception:
            log.error("❌ Could not find Join button.")
        return False

    time.sleep(5)
    return True


def send_chat_message(driver, message):
    """Type a message into the Google Meet chat panel."""
    from selenium.webdriver.common.keys import Keys
    try:
        # ── Step 1: Try to open the chat panel ──
        chat_btn_selectors = [
            "//button[@aria-label='Chat with everyone']",
            "//button[@aria-label='Open chat']",
            "//button[@aria-label='Chat']",
            "//button[contains(@aria-label,'chat')]",
            "//button[contains(@aria-label,'Chat')]",
            "//button[@jsname='A5il2e']",
            "//button[@jsname='W6suGc']",   # ← seen in debug log
            "//button[@jsname='dqt8Pb']",   # ← seen in debug log
            "//button[@jsname='rhHFf']",    # ← seen in debug log
        ]
        for sel in chat_btn_selectors:
            _click_if_present(driver, sel)
        time.sleep(4)

        # ── Step 2: Try all known chat input selectors ──
        chat_input_selectors = [
            "//textarea[@aria-label='Send a message']",
            "//textarea[@aria-label='Message']",
            "//textarea[contains(@aria-label,'message')]",
            "//textarea[contains(@aria-label,'Message')]",
            "//div[@aria-label='Send a message']",
            "//div[@aria-label='Message']",
            "//div[@contenteditable='true'][@aria-label]",
            "//div[@role='textbox']",
            "//div[@contenteditable='true']",
            "//textarea",
        ]

        chat_input = None
        for sel in chat_input_selectors:
            try:
                chat_input = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, sel))
                )
                if chat_input and chat_input.is_displayed():
                    log.info(f"💬 Chat input found via: {sel}")
                    break
                chat_input = None
            except Exception:
                continue

        if not chat_input:
            log.warning("⚠️ Chat input box not found — saving screenshot for debug.")
            driver.save_screenshot("chat_debug.png")
            return

        chat_input.click()
        time.sleep(0.5)
        chat_input.send_keys(message)
        time.sleep(0.5)
        chat_input.send_keys(Keys.RETURN)
        log.info(f"💬 Chat sent: {message[:60]}...")

    except Exception as e:
        log.warning(f"Could not send chat message: {e}")


def _click_if_present(driver, xpath):
    """Click an element if it exists, silently ignore if not."""
    try:
        el = driver.find_element(By.XPATH, xpath)
        el.click()
    except NoSuchElementException:
        pass


def leave_meeting(driver):
    """Click the Leave call button."""
    log.info("Leaving the meeting...")
    _click_if_present(driver, "//button[@aria-label='Leave call']")
    time.sleep(2)
    driver.quit()
    log.info("✅ Left meeting and closed browser.")
