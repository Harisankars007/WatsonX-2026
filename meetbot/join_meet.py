"""
Phase 1: Bot joins Google Meet as a participant using Selenium.
"""

import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from config import MEET_URL, BOT_DISPLAY_NAME, BOT_EMAIL, BOT_PASSWORD

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("MeetBot.Join")


def get_driver():
    """Set up Chrome with required flags for audio capture."""
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

    wait = WebDriverWait(driver, 30)

    # Wait for page to load
    time.sleep(4)

    # ── Dismiss "Got it" / cookie banners if present ──
    for selector in ["//button[contains(text(),'Got it')]",
                     "//button[contains(text(),'Accept all')]"]:
        try:
            btn = driver.find_element(By.XPATH, selector)
            btn.click()
            time.sleep(1)
        except NoSuchElementException:
            pass

    # ── Turn off mic & camera before joining ──
    _click_if_present(driver, "//button[@aria-label='Turn off microphone']")
    _click_if_present(driver, "//button[@aria-label='Turn off camera']")
    time.sleep(1)

    # ── Set display name (guest join) ──
    try:
        name_field = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='Your name']")
        ))
        name_field.clear()
        name_field.send_keys(BOT_DISPLAY_NAME)
        log.info(f"Display name set to: {BOT_DISPLAY_NAME}")
    except TimeoutException:
        log.info("Name field not found — likely signed in already.")

    # ── Click Join / Ask to join ──
    join_buttons = [
        "//button[.//span[contains(text(),'Join now')]]",
        "//button[.//span[contains(text(),'Ask to join')]]",
        "//button[contains(@data-idom-class,'join')]",
    ]
    joined = False
    for xpath in join_buttons:
        try:
            btn = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            btn.click()
            joined = True
            log.info("✅ Joined the meeting!")
            break
        except TimeoutException:
            continue

    if not joined:
        log.error("❌ Could not find Join button.")
        return False

    time.sleep(5)
    return True


def send_chat_message(driver, message):
    """Type a message into the Google Meet chat panel."""
    try:
        wait = WebDriverWait(driver, 10)

        # Open chat if not already open
        _click_if_present(driver, "//button[@aria-label='Chat with everyone']")
        time.sleep(1)

        # Find chat input and type
        chat_input = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//textarea[@aria-label='Send a message']")
        ))
        chat_input.click()
        chat_input.send_keys(message)

        # Send with Enter
        from selenium.webdriver.common.keys import Keys
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
