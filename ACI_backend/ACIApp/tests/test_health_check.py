import pytest
from django.urls import reverse


@pytest.mark.parametrize(
    "url_name",
    ["health-check", "health-check-no-slash"],
)
def test_health_check_is_available_without_authentication(client, url_name):
    response = client.get(reverse(url_name))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
