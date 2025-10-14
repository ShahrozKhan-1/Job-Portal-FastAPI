from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, csv, re, html as html_lib
from datetime import datetime
import sys
import requests


token = sys.argv[1]
job_title = sys.argv[2]
location = sys.argv[3]

print(token, job_title, location)

API_URL = "http://127.0.0.1:8000/add-job"

def save_job_to_api(record, user_token):
    cookies = {"access_token": user_token}
    response = requests.post(API_URL, json=record, cookies=cookies)
    try:
        print("Save response:", response.json())
    except Exception:
        print("Save response (raw):", response.text)

# ---------------- Parser ----------------
def parse_job_content(html):
    text = re.sub(r'<[^>]+>', ' ', html)
    text = html_lib.unescape(re.sub(r'\s+', ' ', text)).strip()
    description, responsibilities, requirements = "", "", ""

    desc_match = re.split(
        r'(Key\s+Responsibilit(?:y|ies)\s*:?|Responsibilit(?:y|ies)\s*:?|Requirement[s]?\s*:?)',
        text, flags=re.I
    )

    if len(desc_match) > 1:
        description = desc_match[0].strip()

        resp_match = re.search(
            r'(Key\s+Responsibilit(?:y|ies)|Responsibilit(?:y|ies))\s*:?\s*(.*?)(?=Requirement[s]?\s*:?|$)',
            text, flags=re.I
        )
        if resp_match:
            responsibilities = resp_match.group(2).strip()

        req_match = re.search(
            r'(Requirement[s]?)\s*:?\s*(.*?)(?=What We Offer|$)',
            text, flags=re.I
        )
        if req_match:
            requirements = req_match.group(2).strip()
    else:
        description = text

    details = {}
    for match in re.finditer(
        r'<div class="row">.*?<b>\s*([^<:]+?)\s*:?\s*</b>.*?<div[^>]*>(.*?)</div>.*?</div>',
        html, re.S | re.I
    ):
        label = match.group(1).strip()
        value_html = match.group(2)
        value_text = re.sub(r'<[^>]+>', ' ', value_html)
        value_text = html_lib.unescape(re.sub(r'\s+', ' ', value_text)).strip(' ,')
        key = label.lower().replace(' ', '_')
        details[key] = value_text

    return {
        "description": description,
        "responsibilities": responsibilities,
        "requirements": requirements,
        "details": details
    }

# ---------------- Helper: Check if job is posted today ----------------
def is_posted_today(posted_text):
    """
    Check if 'Sep 19, 2025' is today's date.
    """
    if not posted_text:
        return False
    try:
        job_date = datetime.strptime(posted_text.strip(), "%b %d, %Y").date()
        return job_date == datetime.today().date()
    except Exception as e:
        print("Date parse error:", e, posted_text)
        return False

# ---------------- Selenium Setup ----------------
custom_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
options = Options()
options.add_argument("--headless=new")
options.add_argument("--enable-unsafe-swiftshader")
options.add_argument("--use-gl=swiftshader")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument(f'--user-agent={custom_user_agent}')

driver = webdriver.Chrome(options=options)
url = f"https://www.rozee.pk/job/jsearch/q/{job_title}/all"
driver.get(url)
time.sleep(2)
locations = driver.find_elements(By.CSS_SELECTOR, "div#fcFacets div.chbx")

for loc in locations:
    label_text = loc.find_element(By.CSS_SELECTOR, ".text-trim").text.strip()
    print("Found location:", label_text)

    if label_text.lower() == location.lower():
        checkbox = loc.find_element(By.CSS_SELECTOR, "input")
        driver.execute_script("arguments[0].checked = true;", checkbox) 
        driver.execute_script("arguments[0].click();", checkbox) 
        print(f"Selected city via input: {location}")
        break


time.sleep(5)

button = driver.find_element(By.CSS_SELECTOR, "button.btn.btn-primary")
driver.execute_script("arguments[0].click();", button)
print("🔎 Search submitted")

time.sleep(5)

# ---------------- Scraping ----------------
jobs_data = []
count = 1
while True:
    jobs = driver.find_elements(By.CSS_SELECTOR, "div#jobs div.job")
    for idx, job in enumerate(jobs):
        driver.execute_script("arguments[0].click();", job)
        time.sleep(2)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "job-content")))
        main_html = driver.find_element(By.ID, "job-content").get_attribute("outerHTML")

        parsed = parse_job_content(main_html)
        details = parsed["details"]

        try:
            salary = driver.find_element(By.CSS_SELECTOR, "div.mrsl.ofa").text
        except:
            salary = None

        try:
            posted_on = job.find_element(By.CSS_SELECTOR, "span[data-original-title='Posted On']").text
        except:
            posted_on = None

        try:
            url = driver.find_element(By.CSS_SELECTOR, "a#copyClipBoard").get_attribute("data-clipboard-text")
        except:
            url = None

        try:
            img_element = driver.find_element(By.CSS_SELECTOR, "div.logo img")
            logo = img_element.get_attribute("src")
        except:
            logo = None

        try:
            job_content = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "job-content"))
            )

            jblk_divs = job_content.find_elements(By.XPATH, "./div[@class='jblk']")

            if len(jblk_divs) > 1:
                skills_div = jblk_divs[1]
                skills = [a.text.strip() for a in skills_div.find_elements(By.TAG_NAME, "a")]
                print(skills)
            else:
                print("No skills section found")

        except Exception as e:
            print("Error:", e)


        record = {
            "source":"rozee.pk",
            "link": url,
            "logo":logo,
            "title": driver.find_element(By.CSS_SELECTOR, "h1.jtitle").text,
            "company": driver.find_element(By.CSS_SELECTOR, "h2.cname").text,
            "location": details.get("job_location", ""),
            "salary": salary,
            "description": parsed["description"],
            "seniority_level": details.get("career_level", ""),
            "employment_type": details.get("job_type", ""),
            "job_function": details.get("functional_area", ""),
            "industry": details.get("industry", ""),
            "requirements": parsed["requirements"],
            "responsibilities": parsed["responsibilities"],
            "skills": skills,
            "posted_on": posted_on
        }

        print(f"{record['title']} is posted on {record["posted_on"]}")

        if is_posted_today(posted_on):
            save_job_to_api(record, user_token=token)
            jobs_data.append(record)
            print(f"Added: {record['title']} ({record['posted_on']})")
        else:
            print(f"Skipped (not today): {record['title']} ({record['posted_on']})")


    try:
        next_btns = driver.find_elements(By.CSS_SELECTOR, "ul.pagination a.next")
        next_btn = next_btns[-1] 
        driver.execute_script("arguments[0].click();", next_btn)
        if count == 2:
            break
        count += 1
        time.sleep(3) 
    except:
        print("No more pages.")
        break

# ---------------- Save to CSV ----------------
fieldnames = [
    "link", "logo", "source", "title", "company", "location", "salary", "description",
    "seniority_level", "employment_type", "job_function", "industry",
    "requirements", "responsibilities", "skills", "posted_on"
]

with open("rozee_jobs_today.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(jobs_data)

driver.quit()
print(f"Saved {len(jobs_data)} jobs (today only) to rozee_jobs_today.csv")

