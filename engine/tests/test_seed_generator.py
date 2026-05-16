import hashlib

from engine.vibes.seed_generator import SEED_LENGTH, generate_seed


def test_deterministic():
    a = generate_seed("feeling lucky", [7, 23, 11])
    b = generate_seed("feeling lucky", [7, 23, 11])
    assert a == b


def test_length():
    seed = generate_seed("anything", [1])
    assert len(seed) == SEED_LENGTH
    assert all(c in "0123456789abcdef" for c in seed)


def test_text_change_changes_seed():
    a = generate_seed("hot", [7])
    b = generate_seed("cold", [7])
    assert a != b


def test_number_change_changes_seed():
    a = generate_seed("vibe", [7, 23])
    b = generate_seed("vibe", [23, 7])  # order matters per spec
    assert a != b


def test_empty_inputs_still_produce_seed():
    seed = generate_seed("", [])
    assert len(seed) == SEED_LENGTH


def test_matches_documented_formula():
    text = "feeling lucky tonight"
    numbers = [7, 23, 11]
    expected = hashlib.sha256(b"feeling lucky tonight:7,23,11").hexdigest()[:SEED_LENGTH]
    assert generate_seed(text, numbers) == expected


def test_single_number_no_trailing_comma():
    expected = hashlib.sha256(b"x:42").hexdigest()[:SEED_LENGTH]
    assert generate_seed("x", [42]) == expected
