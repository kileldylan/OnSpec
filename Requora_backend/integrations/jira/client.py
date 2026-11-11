import requests

from django.conf import settings


class JiraAPIError(Exception):
	"""Raised when Jira cannot provide a usable issue response."""


class JiraClient:
	"""Small Jira REST client for issue retrieval."""

	def __init__(self, *, base_url=None, email=None, api_token=None, timeout=None):
		self.base_url = (base_url or settings.JIRA_BASE_URL).rstrip("/")
		self.email = email or settings.JIRA_EMAIL
		self.api_token = api_token or settings.JIRA_API_TOKEN
		self.timeout = timeout or settings.JIRA_API_TIMEOUT
		self.session = requests.Session()

	def get_issue(self, issue_key):
		if not self.base_url or not self.api_token:
			raise JiraAPIError("Jira credentials are not configured.")
		response = self.session.get(
			f"{self.base_url}/rest/api/3/issue/{issue_key}",
			auth=(self.email, self.api_token),
			headers={"Accept": "application/json"},
			timeout=self.timeout,
		)
		try:
			response.raise_for_status()
			payload = response.json()
		except requests.RequestException as error:
			if response.status_code == 404:
				raise JiraAPIError(f"Jira issue {issue_key} was not found.") from error
			raise JiraAPIError(
				f"Jira returned an unusable response for {issue_key}."
			) from error
		except ValueError as error:
			raise JiraAPIError(
				f"Jira issue payload for {issue_key} is malformed."
			) from error
		if not isinstance(payload, dict) or "key" not in payload:
			raise JiraAPIError(f"Jira issue response for {issue_key} is malformed.")
		return payload
