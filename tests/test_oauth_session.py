from app.services.oauth_session import pop_oauth_session, put_oauth_session
from app.services.oauth_state import generate_state


def test_oauth_session_is_single_use():
    state = generate_state()
    put_oauth_session(state, provider="tiktok", creator_id=1, code_verifier="x" * 43)
    data = pop_oauth_session(state)
    assert data is not None
    assert data["provider"] == "tiktok"
    assert pop_oauth_session(state) is None
