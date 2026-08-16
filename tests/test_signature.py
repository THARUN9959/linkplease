from app.services.signature import compute_signature, verify_signature


def test_signature_roundtrip():
    body = b'{"event_id":"evt_1"}'
    secret = "test-secret"
    header = compute_signature(body, secret)
    assert header.startswith("sha256=")
    assert verify_signature(body, header, secret)


def test_signature_rejects_tampered_body():
    secret = "test-secret"
    header = compute_signature(b'{"ok":true}', secret)
    assert not verify_signature(b'{"ok":false}', header, secret)


def test_signature_rejects_missing_header():
    assert not verify_signature(b"{}", None, "secret")
    assert not verify_signature(b"{}", "", "secret")
