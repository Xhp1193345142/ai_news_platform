from uuid import uuid4

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_is_argon2_hashed_and_verifiable() -> None:
    password_hash = hash_password("a-strong-password")

    assert password_hash != "a-strong-password"
    assert verify_password("a-strong-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_contains_the_authenticated_user() -> None:
    user_id = uuid4()
    token, expires_in = create_access_token(user_id)

    assert expires_in > 0
    assert decode_access_token(token) == user_id
