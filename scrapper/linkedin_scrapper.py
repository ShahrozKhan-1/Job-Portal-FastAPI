from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import sys
import requests


token = sys.argv[1]
job_title = sys.argv[2]
job_location = sys.argv[3]

API_URL = "http://127.0.0.1:8000/add-job"

def save_job_to_api(record, user_token):
    cookies = {"access_token": user_token}
    response = requests.post(API_URL, json=record, cookies=cookies)
    try:
        print("Save response:", response.json())
    except Exception:
        print("Save response (raw):", response.text)


# ----------------- Helpers -----------------
def parse_job_content(raw_text: str) -> dict:
    """
    Extract description, responsibilities, requirements, and skills.
    """
    if not raw_text:
        return {
            "description": None,
            "responsibilities": None,
            "requirements": None,
            "skills": None,
        }

    text = re.sub(r"\s+", " ", raw_text).strip()

    # Section headers
    responsibilities_patterns = [
        "responsibilities", "responsibility", "duties", "tasks",
        "what you will do", "job duties", "role overview"
    ]
    requirements_patterns = [
        "requirements", "requirement", "qualification", "qualifications",
        "eligibility", "experience needed", "must have"
    ]
    skills_patterns = [
        "skills", "desired skills", "technical skills", "competencies",
        "knowledge", "expertise"
    ]

    description, responsibilities, requirements, skills = text, None, None, None
    matches = []

    for label, patterns in [
        ("responsibilities", responsibilities_patterns),
        ("requirements", requirements_patterns),
        ("skills", skills_patterns),
    ]:
        match = re.search(rf"({'|'.join(patterns)})", text, re.I)
        if match:
            matches.append((label, match.start()))

    matches.sort(key=lambda x: x[1])

    if matches:
        description = text[:matches[0][1]].strip()
        for i, (label, start) in enumerate(matches):
            end = matches[i + 1][1] if i + 1 < len(matches) else None
            section_text = text[start:end].strip()
            if label == "responsibilities":
                responsibilities = section_text
            elif label == "requirements":
                requirements = section_text
            elif label == "skills":
                skills = section_text

    def clean_section(s):
        if not s:
            return None
        return re.sub(
            r"^(Responsibilities?|Duties|Tasks|Requirements?|Qualifications?|Skills|Competencies|Knowledge)[:\-]?\s*",
            "",
            s,
            flags=re.I,
        ).strip()

    return {
        "description": description,
        "responsibilities": clean_section(responsibilities),
        "requirements": clean_section(requirements),
        "skills": clean_section(skills),
    }


def parse_job_criteria(driver):
    """
    Extract seniority level, employment type, job function, industry.
    """
    criteria = {"seniority_level": None, "employment_type": None,
                "job_function": None, "industry": None}

    try:
        items = driver.find_elements(By.CSS_SELECTOR, "ul.description__job-criteria-list li")
        for item in items:
            try:
                header = item.find_element(By.CSS_SELECTOR, "h3").text.strip().lower()
                value = item.find_element(By.CSS_SELECTOR, "span").text.strip()
                if "seniority" in header:
                    criteria["seniority_level"] = value
                elif "employment" in header:
                    criteria["employment_type"] = value
                elif "function" in header:
                    criteria["job_function"] = value
                elif "industr" in header:
                    criteria["industry"] = value
            except:
                continue
    except:
        pass

    return criteria


# ----------------- Scraper -----------------
def scrape_linkedin_jobs(max_jobs=20, pages=1):
    options = webdriver.ChromeOptions()
    custom_user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
    options.add_argument(f'--user-agent={custom_user_agent}')
    
    # options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--enable-unsafe-swiftshader")
    options.add_argument("--use-gl=swiftshader")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)

    driver.get(
        f"https://www.linkedin.com/jobs/search?keywords={job_title}&location=Pakistan&geoId=101022442&f_TPR=r86400&position=1&pageNum=0"
    )
    time.sleep(3)
    loc_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Location filter. Clicking this button displays all Location filter options.']")
    driver.execute_script("arguments[0].click();", loc_btn)
    time.sleep(2)
    loc_search = driver.find_element(By.CSS_SELECTOR, "input#f_PP")
    loc_search.clear()
    loc_search.send_keys(job_location)
    time.sleep(2)
    loc_search.send_keys(Keys.DOWN)
    time.sleep(2)
    loc_search.send_keys(Keys.ENTER)
    time.sleep(2)
    done_button = driver.find_element(By.CSS_SELECTOR, "button.filter__submit-button")
    driver.execute_script("arguments[0].click();", done_button)


    job_links = set()
    
    for _ in range(pages):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        cards = soup.select("a.base-card__full-link")
        for card in cards:
            job_links.add(card["href"])

        try:
            load_more = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='See more results']"))
            )
            load_more.click()
        except:
            pass

    job_links = list(job_links)[:max_jobs]

    jobs = []
    for link in job_links:
        driver.get(link)
        time.sleep(2)
        try:
            show_more_btn = driver.find_element(By.CSS_SELECTOR, "button.show-more-less-html__button--more")
            driver.execute_script("arguments[0].click();", show_more_btn)
            time.sleep(1)
        except:
            print("No 'Show more' button found.") 

        soup = BeautifulSoup(driver.page_source, "html.parser")

        title = soup.select_one("h1.top-card-layout__title")
        company = soup.select_one("a.topcard__org-name-link, span.topcard__flavor")
        location = soup.select_one("span.topcard__flavor--bullet")
        posted_on = soup.select_one("span.posted-time-ago__text")
        salary_tag = soup.select_one("div.salary")

        title = title.text.strip() if title else None
        company = company.text.strip() if company else None
        location = location.text.strip() if location else None
        posted_on = posted_on.text.strip() if posted_on else None
        salary = salary_tag.text.strip() if salary_tag else None

        try:
            desc = soup.find("div", class_="description__text").text.strip()
        except:
            desc = None

        try:
            logo_tag = soup.select_one("div.top-card-layout__card a img.artdeco-entity-image")
            logo_url = logo_tag["src"]
        except:
            logo_url = "N/A"

        sections = parse_job_content(desc)
        criteria = parse_job_criteria(driver)

        new_job = {
            "source":"linkedin",
            "link": link,
            "logo":logo_url,
            "title": title,
            "company": company,
            "location": location,
            "salary": salary,
            "description": sections["description"],
            "responsibilities": sections["responsibilities"],
            "requirements": sections["requirements"],
            "skills": [sections["skills"]] if sections["skills"] else [],
            "seniority_level": criteria.get("seniority_level"),
            "employment_type": criteria.get("employment_type"),
            "job_function": criteria.get("job_function"),
            "industry": criteria.get("industry"),
            "posted_on": posted_on,
        }
        jobs.append(new_job)
        print(new_job)
        save_job_to_api(new_job, token)
    driver.quit()
    return jobs


# ----------------- Save -----------------
def save_job_data(data):
    pd.DataFrame(data).to_csv("linkedin_jobs.csv", index=False)


# ----------------- Run -----------------
if __name__ == "__main__":
    data = scrape_linkedin_jobs(max_jobs=50, pages=3)
    save_job_data(data)
    print(f"Saved {len(data)} jobs to linkedin_jobs.csv")
