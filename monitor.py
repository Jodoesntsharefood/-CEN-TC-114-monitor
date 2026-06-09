import os
import json
import requests

from playwright.sync_api import sync_playwright

URL = "https://standards.cencenelec.eu/ords/f?p=CEN:110:::::FSP_PROJECT,FSP_ORG_ID:71234,6096"

STATUS_FILE = "last_status.json"


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

        page.wait_for_timeout(10000)

        tables = page.locator("table")

        table_count = tables.count()

        print(f"Found tables: {table_count}")

        found = False

        for t in range(table_count):

            table = tables.nth(t)

            rows = table.locator("tr")

            row_count = rows.count()

            if row_count < 2:
                continue

            headers = [
                x.strip()
                for x in rows.nth(0).inner_text().split("\n")
                if x.strip()
            ]

            try:

                ref_idx = next(
                    i
                    for i, h in enumerate(headers)
                    if "reference" in h.lower()
                )

                title_idx = next(
                    i
                    for i, h in enumerate(headers)
                    if "title" in h.lower()
                )

                status_idx = next(
                    i
                    for i, h in enumerate(headers)
                    if "status" in h.lower()
                )

            except StopIteration:
                continue

            print("Work programme table found")

            found = True

            for r in range(1, row_count):

                row = rows.nth(r)

                cols = [
                    x.strip()
                    for x in row.inner_text().split("\n")
                    if x.strip()
                ]

                if len(cols) <= max(
                    ref_idx,
                    title_idx,
                    status_idx
                ):
                    continue

                reference = cols[ref_idx]
                title = cols[title_idx]
                status = cols[status_idx]

                key = f"{reference} | {title}"

                results[key] = status

        browser.close()

        if not found:
            raise Exception(
                "Cannot locate Work Programme table"
            )

    return results


def load_old_statuses():

    if not os.path.exists(STATUS_FILE):
        return {}

    with open(
        STATUS_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


def save_statuses(statuses):

    with open(
        STATUS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            statuses,
            f,
            indent=2,
            ensure_ascii=False
        )


def compare_statuses(old, new):

    changes = []

    all_keys = set(old.keys()) | set(new.keys())

    for key in all_keys:

        old_status = old.get(key)
        new_status = new.get(key)

        if old_status != new_status:

            changes.append(
                (
                    key,
                    old_status,
                    new_status
                )
            )

    return changes


def send_email(changes):

    resend_api_key = os.environ["RESEND_API_KEY"]

    to_emails = (
        os.environ["TO_EMAILS"]
        .split(",")
    )

    html = """
    <h2>CEN Work Programme Changes</h2>
    """

    for item, old_status, new_status in changes:

        html += f"""
        <hr>

        <p>
        <b>Standard:</b><br>
        {item}
        </p>

        <p>
        <b>Old Status:</b>
        {old_status}
        </p>

        <p>
        <b>New Status:</b>
        {new_status}
        </p>
        """

    html += f"""
    <br>
    <a href="{URL}">
    Open Work Programme
    </a>
    """

    payload = {
        "from":
            "CEN Monitor <onboarding@resend.dev>",

        "to":
            to_emails,

        "subject":
            "[CEN Alert] Status Changed",

        "html":
            html,
    }

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization":
                f"Bearer {resend_api_key}",
            "Content-Type":
                "application/json",
        },
        json=payload,
    )

    print(response.status_code)
    print(response.text)


def main():

    current_statuses = get_current_statuses()

    print(
        json.dumps(
            current_statuses,
            indent=2,
            ensure_ascii=False
        )
    )

    old_statuses = load_old_statuses()

    changes = compare_statuses(
        old_statuses,
        current_statuses
    )

    if not old_statuses:

        print(
            "First run. Save baseline."
        )

        save_statuses(current_statuses)

        return

    if changes:

        print("Changes detected")

        send_email(changes)

        save_statuses(current_statuses)

    else:

        print("No changes")


if __name__ == "__main__":
    main()
