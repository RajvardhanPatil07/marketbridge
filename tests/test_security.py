from marketbridge.security import NonceStore, SignatureHeaders, SlidingWindowLimiter, sign_request, verify_signature


def test_hmac_signature_round_trip_and_tamper_rejection():
    body = b'{"symbol":"NVDA","mark_price":200}'
    signature = sign_request("secret", "100", "nonce-1", body)
    headers = SignatureHeaders("100", "nonce-1", signature)
    assert verify_signature("secret", headers, body)
    assert not verify_signature("secret", headers, body + b" ")


def test_nonce_store_rejects_replay_and_allows_after_ttl():
    store = NonceStore(ttl_seconds=2)
    assert store.use_once("abc", now=10)
    assert not store.use_once("abc", now=11)
    assert store.use_once("abc", now=13)


def test_sliding_window_limiter_is_bounded_per_key():
    limiter = SlidingWindowLimiter(limit=2, window_seconds=10)
    assert limiter.allow("client", now=1)
    assert limiter.allow("client", now=2)
    assert not limiter.allow("client", now=3)
    assert limiter.allow("client", now=12)
