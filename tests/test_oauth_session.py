from app.services.oauth_session import pop_oauth_session, put_oauth_session
from app.services.oauth_state import generate_state


async def test_oauth_session_is_single_use(db):
    state = generate_state()
    await put_oauth_session(state, db, provider="tiktok", creator_id=1, code_verifier="x" * 43)
    data = await pop_oauth_session(state, db)
    assert data is not None
    assert data["provider"] == "tiktok"
    assert await pop_oauth_session(state, db) is None
