import os
import json
import requests
from playwright.sync_api import sync_playwright

URL = "https://standards.cencenelec.eu/ords/f?p=205:22:::::FSP_ORG_ID,FSP_LANG_ID:6096,25&cs=1F04225AC4AA8A8F6528296534D92864B"

STATUS_FILE = "last_status.json"

STATUS_CANDIDATES = [
    "Preliminary",
    "Under Drafting",
    "Under Approval",
    "Under Enquiry",
    "Published",
    "Withdrawn"
]


def get_current_statuses():
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        page.goto(
            URL,
            wait_until="networkidle",
            timeout=120000
        )

        page.wait_for_timeout(8000)

        rows = page.locator("table tr")

        count = rows.count()

        print(f"Found rows: {count}")

        for i in range(count):
            row = rows.nth(i)

            try:
                text = row.inner_text().strip()
            except Exception:
                continue

            if not text:
                continue

            cols = [c.strip() for c in text.split("\n") if c.strip()]

            if len(cols) < 2:
                continue

            work_item = cols[0]

            detected_status = None

            for col in cols:
                for status in STATUS_CANDIDATES:
                    if status.lower() in col.lower():
                        detected_status = status
                        break

                if detected_status:
                    break

            if detected_status:
                results[work_item] = detected_status

        browser.close()

    return results


def load_old_statuses():
    if not os.path.exists(STATUS_FILE):
        return {}

    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_statuses(statuses):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            statuses,
            f,
            indent=2,
            ensure_ascii=False
        )


def compare_statuses(old, new):
    changes = []

    all_keys = set(old.keys()) | set(new.keys())

    for key in sorted(all_keys):
        old_status = old.get(key)
        new_status = new.get(key)

        if old_status != new_status:
            changes.append(
                (key, old_status, new_status)
            )

    return changes


def send_email(changes):
    resend_api_key = os.environ["RESEND_API_KEY"]

    to_emails = [
        x.strip()
        for x in os.environ["TO_EMAILS"].split(",")
        if x.strip()
    ]

    html = "<h2>CEN/TC114 Status Changes</h2>"

    for item, old_status, new_status in changes:
        html += f"""
        <hr>
        <p><b>Work Item:</b> {item}</p>
        <p><b>Old Status:</b> {old_status}</p>
        <p><b>New Status:</b> {new_status}</p>
        """

    html += f"""
    <hr>
    <p>
      <a href="{URL}">
        Open TC114 page
      </a>
    </p>
    """

    payload = {
        "from": "onboarding@resend.dev",
        "to": to_emails,
        "subject": "[CEN/TC114] Status Changed",
        "html": html
    }

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json"
        },
        json=payload
    )

    print("Email status code:", response.status_code)
    print("Email response:", response.text)

    response.raise_for_status()


def main():
    current_statuses = get_current_statuses()

    print("========== CURRENT ==========")
    print(
        json.dumps(
            current_statuses,
            indent=2,
            ensure_ascii=False
        )
    )

    # 仅在完全抓不到数据时终止
    if len(current_statuses) == 0:
        print("No standards found.")
        return

    old_statuses = load_old_statuses()

    print("========== OLD ==========")
    print(
        json.dumps(
            old_statuses,
            indent=2,
            ensure_ascii=False
        )
    )

    changes = compare_statuses(
        old_statuses,
        current_statuses
    )

    if not old_statuses:
        print("First run detected.")

        save_statuses(current_statuses)

        print("Baseline saved.")

        return

    if changes:
        print("========== CHANGES ==========")

        for c in changes:
            print(c)

        send_email(changes)

        save_statuses(current_statuses)

        print("Status file updated.")

    else:
        print("No changes detected.")

        save_statuses(current_statuses)


if __name__ == "__main__":
    main()
