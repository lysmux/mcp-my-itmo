import re
from mcp_my_itmo.auth.pkce import make_verifier, make_challenge, make_state


class TestMakeVerifier:
    def test_verifier_length_in_range(self):
        verifier = make_verifier()
        assert 43 <= len(verifier) <= 128

    def test_verifier_uses_unreserved_characters(self):
        verifier = make_verifier()
        allowed_pattern = r'^[A-Za-z0-9\-._~]+$'
        assert re.match(allowed_pattern, verifier)

    def test_verifier_is_random(self):
        verifiers = [make_verifier() for _ in range(10)]
        assert len(set(verifiers)) == len(verifiers)


class TestMakeChallenge:
    def test_challenge_with_rfc_test_vector(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        expected_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        assert make_challenge(verifier) == expected_challenge

    def test_challenge_is_base64url_without_padding(self):
        verifier = make_verifier()
        challenge = make_challenge(verifier)
        assert "=" not in challenge
        assert re.match(r'^[A-Za-z0-9\-_]+$', challenge)


class TestMakeState:
    def test_state_is_distinct(self):
        states = [make_state() for _ in range(10)]
        assert len(set(states)) == len(states)

    def test_state_is_not_empty(self):
        state = make_state()
        assert len(state) > 0
