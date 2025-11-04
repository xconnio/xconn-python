import pytest

from xconn import Client
from tests.utils import ROUTER_URL, REALM


@pytest.mark.timeout(10)
@pytest.mark.parametrize("url", ROUTER_URL)
def test_session_leave(url: str):
    client = Client()
    session = client.connect(url, REALM)
    session.leave()
