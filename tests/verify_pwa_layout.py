import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

mobile_emulation = {
    'deviceMetrics': {'width': 390, 'height': 844, 'pixelRatio': 3.0},
    'userAgent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
}
chrome_options.add_experimental_option('mobileEmulation', mobile_emulation)

driver = webdriver.Chrome(options=chrome_options)
try:
    driver.get('http://127.0.0.1:8080')
    time.sleep(2)
    
    # Check mainNav
    nav = driver.find_element(By.ID, 'mainNav')
    nr = nav.rect
    print(f'Nav rect: x={nr["x"]}, y={nr["y"]}, w={nr["width"]}, h={nr["height"]}')
    
    buttons = nav.find_elements(By.TAG_NAME, 'button')
    print(f'Total nav buttons: {len(buttons)}')
    for i, btn in enumerate(buttons):
        r = btn.rect
        text = btn.text.replace('\n', ' ')
        view = btn.get_attribute('data-view')
        displayed = btn.is_displayed()
        print(f'  Btn {i+1}: view={view} displayed={displayed} x={r["x"]} y={r["y"]} w={r["width"]} h={r["height"]}')
        
    win_h = driver.execute_script('return window.innerHeight')
    win_w = driver.execute_script('return window.innerWidth')
    body_h = driver.execute_script('return document.body.offsetHeight')
    gap = win_h - (nr['y'] + nr['height'])
    print(f'Window: {win_w}x{win_h}, Body height: {body_h}, Gap below nav: {gap}px')
    
    # Test Standalone PWA mode injection
    driver.execute_script('document.documentElement.classList.add("is-pwa-standalone"); document.body.classList.add("is-pwa-standalone");')
    time.sleep(0.5)
    nr_standalone = nav.rect
    gap_standalone = win_h - (nr_standalone['y'] + nr_standalone['height'])
    print(f'Standalone Mode: nav y={nr_standalone["y"]} h={nr_standalone["height"]}, Gap below nav: {gap_standalone}px')
    
    driver.save_screenshot(r'C:\Users\kiemp\.gemini\antigravity\brain\a1a21ac4-d045-4b4f-9777-dc76104a515d\proof_pwa_fix_verified.png')
    print('Screenshot saved successfully')

finally:
    driver.quit()
