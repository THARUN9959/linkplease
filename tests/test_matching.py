from app.services.events import comment_matches_rule


def test_keyword_matches_anywhere_case_insensitive():
    assert comment_matches_rule("PRICE please", "price")
    assert comment_matches_rule("please price now", "price")
    assert comment_matches_rule("PrIcE", "price")
    assert not comment_matches_rule("hello", "price")
    assert comment_matches_rule("xxPRICEyy", "price")
