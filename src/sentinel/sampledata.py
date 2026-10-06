"""Deterministic sample dataset: two deployment versions of the same pipeline.

The story: an upstream LLM step summarizes and categorizes support tickets.
Between v1 and v2 someone "improved" the prompt and silently regressed it, so v2
summaries no longer address the actual ticket. BOTH versions pass every
deterministic check (non-null, valid category enum, unique ids, fresh
timestamps) -- the drift is purely semantic. That is exactly the failure the
deterministic BigQuery checks cannot see.

No randomness: the dataset is identical on every machine so the live demo is
reproducible on stage.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

VALID_CATEGORIES = ["billing", "technical", "account", "other"]


@dataclass
class Ticket:
    row_id: str
    deployment_version: str
    ticket_text: str
    category: str
    resolution_summary: str
    created_at: str  # ISO date; all recent so freshness passes


# 13 realistic tickets. For each we author a GOOD resolution (v1) and a
# plausible-but-off resolution (v2) that still mentions product words, so it
# looks fine to a keyword skim but does not address the issue.
_BASE = [
    (
        "I was charged twice for my October subscription and need one refunded.",
        "billing",
        "Confirmed the duplicate October charge and issued a refund for the "
        "extra subscription payment; it will post in 3-5 business days.",
        "Thanks for reaching out about your subscription. You can view all "
        "invoices in the billing dashboard under Account Settings.",
    ),
    (
        "The export button throws a 500 error every time I click it.",
        "technical",
        "Reproduced the 500 on export, traced it to a timeout in the report "
        "service, deployed a fix, and verified export now completes.",
        "Exports are a popular feature. Make sure you are on the latest version "
        "and have a stable internet connection for best results.",
    ),
    (
        "I can't log in, it says my account is locked after a password reset.",
        "account",
        "Unlocked the account that was flagged by the reset flow and sent a "
        "fresh reset link; confirmed the customer logged in successfully.",
        "Account security is important to us. We recommend enabling two-factor "
        "authentication to keep your account safe.",
    ),
    (
        "My invoice shows the wrong company name and I need it corrected.",
        "billing",
        "Updated the billing profile company name and reissued the corrected "
        "invoice PDF for the current period.",
        "Invoices are generated automatically each month. You can download them "
        "any time from the billing section.",
    ),
    (
        "The mobile app crashes on startup after the latest update.",
        "technical",
        "Identified a null-state crash on cold start in the latest build, "
        "shipped a hotfix, and confirmed the app launches cleanly.",
        "We release updates regularly to improve the mobile experience. Please "
        "keep auto-update enabled in your app store.",
    ),
    (
        "I was promised a 20% discount but it wasn't applied at checkout.",
        "billing",
        "Found the missing promo on the order, applied the 20% discount "
        "retroactively, and refunded the difference to the card on file.",
        "Discounts and promotions appear on our pricing page from time to time. "
        "Sign up for the newsletter to hear about offers.",
    ),
    (
        "API returns 401 even with a freshly generated key.",
        "technical",
        "Found the new key was scoped to the wrong project; regenerated it with "
        "the correct scope and confirmed authenticated calls succeed.",
        "Our API is well documented. Review the authentication guide and ensure "
        "your request includes the Authorization header.",
    ),
    (
        "Please delete my account and all associated data per my request.",
        "account",
        "Verified identity, queued the account and associated data for deletion "
        "within 30 days, and sent written confirmation.",
        "We value your privacy. Our privacy policy explains how we handle and "
        "store customer data across our services.",
    ),
    (
        "You charged my old card instead of the new one I added.",
        "billing",
        "Set the newly added card as default, voided the charge on the old "
        "card, and reprocessed payment on the correct card.",
        "You can manage saved payment methods under Billing. Adding a card does "
        "not remove older ones automatically.",
    ),
    (
        "Search results are completely empty even for exact title matches.",
        "technical",
        "Found the search index had not rebuilt after migration; triggered a "
        "reindex and confirmed exact-title queries return results.",
        "Search works best with specific keywords. Try narrowing your query and "
        "using filters to improve relevance.",
    ),
    (
        "I need to transfer ownership of the workspace to a colleague.",
        "account",
        "Transferred workspace ownership to the specified colleague after "
        "admin confirmation and verified their new owner permissions.",
        "Workspaces support multiple roles. Admins can be added from the team "
        "settings page whenever you need them.",
    ),
    (
        "The dashboard shows last week's numbers, not today's.",
        "technical",
        "Traced stale dashboard data to a broken nightly ETL job, re-ran it, "
        "and confirmed the dashboard now reflects today's numbers.",
        "Dashboards refresh periodically. You can also click refresh in the top "
        "right to pull the latest view.",
    ),
    (
        "Cancel my plan; I do not want to be billed next cycle.",
        "billing",
        "Cancelled the plan effective end of the current cycle and confirmed no "
        "further charges will occur; sent a cancellation receipt.",
        "We are sorry to see you go. Plans can be changed or cancelled at any "
        "time from the subscription page.",
    ),
]


def generate(version: str) -> list[Ticket]:
    """Return the tickets for a deployment version ('v1' or 'v2')."""
    use_good = version == "v1"
    rows: list[Ticket] = []
    for i, (text, cat, good, drifted) in enumerate(_BASE):
        rows.append(
            Ticket(
                row_id=f"TCK-{i:03d}",
                deployment_version=version,
                ticket_text=text,
                category=cat,  # category stays valid in both versions
                resolution_summary=good if use_good else drifted,
                created_at="2026-10-05",
            )
        )
    return rows


def all_rows() -> list[dict]:
    return [asdict(t) for t in (generate("v1") + generate("v2"))]
