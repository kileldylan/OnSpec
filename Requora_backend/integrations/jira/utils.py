import re


JIRA_ISSUE_PATTERN = re.compile(
    r"\b[A-Z][A-Z0-9]+-\d+\b"
)


def extract_jira_issue_keys(text):
    """
    Extract Jira issue keys from arbitrary text.

    Example:
        "Implements PROJ-123 and fixes PROJ-456"
        -> ["PROJ-123", "PROJ-456"]
    """

    if not text:
        return []

    return list(
        dict.fromkeys(
            JIRA_ISSUE_PATTERN.findall(text)
        )
    )