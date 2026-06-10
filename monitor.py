import os
import json
import requests

from playwright.sync_api import sync_playwright

URL = "https://standards.cencenelec.eu/ords/f?p=CEN:110:::::FSP_PROJECT,FSP_ORG_ID:71234,6096"

STATUS_FILE = "last_status.json"


def get_current_statuses():

    results = {}

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )
        )

        page = context.new_page()

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=120000
        )

        page.wait_for_timeout(15000)

        print("Current URL:")
        print(page.url)

        print("Page Title:")
        print(page.title())

        page.screenshot(
            path="debug.png",
            full_page=True
        )

        with open(
            "debug.html",
            "w",
            encoding="utf-8"
        ) as f:
            f.write(page.content())

        try:

            page.wait_for_selector(
                "#DASHBOARD_LISTTCWORKPROG",
                timeout=30000
            )

        except Exception:

            browser.close()

            raise Exception(
                "Cannot find "
                "#DASHBOARD_LISTTCWORKPROG"
            )

        rows = page.locator(
            "#DASHBOARD_LISTTCWORKPROG tr"
        )

        row_count = rows.count()

        print(
            f"Rows found: {row_count}"
        )

        for i in range(1, row_count):

            row = rows.nth(i)

            cells = row.locator("td")

            if cells.count() < 3:
                continue

            try:

                reference = (
                    cells.nth(0)
                    .inner_text()
                    .strip()
                )

                status = (
                    cells.nth(1)
                    .inner_text()
                    .strip()
                )

                title = (
                    cells.nth(2)
                    .inner_text()
                    .strip()
                )

                key = (
                    f"{reference} | {title}"
                )

                results[key] = status

            except Exception as e:

                print(
                    f"Skip row {i}: {e}"
                )

        browser.close()

    print(
        f"Collected {len(results)} projects"
    )

    return results


def load_old_statuses():

    if not os.path.exists(
        STATUS_FILE
    ):
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

    keys = (
        set(old.keys())
        | set(new.keys())
    )

    for key in keys:

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

    api_key = os.environ[
        "RESEND_API_KEY"
    ]

    recipients = (
        os.environ["TO_EMAILS"]
        .split(",")
    )

    html = """
    <h2>
    CEN Work Programme Change
    </h2>
    """

    for key, old_s, new_s in changes:

        html += f"""
        <hr>

        <p>
        <b>{key}</b>
        </p>

        <p>
        {old_s}
        →
        {new_s}
        </p>
        """

    requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization":
                f"Bearer {api_key}",
            "Content-Type":
                "application/json"
        },
        json={
            "from":
                "CEN Monitor <onboarding@resend.dev>",
            "to":
                recipients,
            "subject":
                "[CEN Alert] Status Change",
            "html":
                html
        }
    )


def main():

    current = get_current_statuses()

    old = load_old_statuses()

    if not old:

        print(
            "First run. "
            "Creating baseline."
        )

        save_statuses(current)

        return

    changes = compare_statuses(
        old,
        current
    )

    if changes:

        print(
            f"Changes found: "
            f"{len(changes)}"
        )

        send_email(changes)

        save_statuses(current)

    else:

        print("No changes")


if __name__ == "__main__":
    main()
