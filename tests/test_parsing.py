"""Unit tests for app.parsing."""

import pytest
from app.parsing import parse_transaction


class TestParseTransaction:
    """Test the transaction parser."""

    # ------------------------------------------------------------------ #
    # Valid transactions
    # ------------------------------------------------------------------ #

    def test_simple_integer(self):
        result = parse_transaction("15 to jazz13gv")
        assert result is not None
        assert result.amount == 15.0
        assert result.person == "jazz13gv"

    def test_decimal_amount(self):
        result = parse_transaction("10.5 to quanshan13gv")
        assert result is not None
        assert result.amount == 10.5
        assert result.person == "quanshan13gv"

    def test_case_insensitive_to(self):
        result = parse_transaction("20 TO alice")
        assert result is not None
        assert result.amount == 20.0
        assert result.person == "alice"

    def test_mixed_case_to(self):
        result = parse_transaction("30 To Bob")
        assert result is not None
        assert result.amount == 30.0
        assert result.person == "Bob"

    def test_extra_spaces(self):
        result = parse_transaction("  50   to   charlie  ")
        assert result is not None
        assert result.amount == 50.0
        assert result.person == "charlie"

    def test_large_amount(self):
        result = parse_transaction("100000 to bigspender")
        assert result is not None
        assert result.amount == 100000.0

    def test_person_with_spaces(self):
        result = parse_transaction("25 to John Doe")
        assert result is not None
        assert result.person == "John Doe"

    def test_zero_decimal(self):
        result = parse_transaction("100.00 to exact")
        assert result is not None
        assert result.amount == 100.0

    # ------------------------------------------------------------------ #
    # Invalid / non-matching
    # ------------------------------------------------------------------ #

    def test_empty_string(self):
        assert parse_transaction("") is None

    def test_none_like(self):
        assert parse_transaction("") is None  # falsy

    def test_no_to_keyword(self):
        assert parse_transaction("15 jazz13gv") is None

    def test_no_amount(self):
        assert parse_transaction("to jazz13gv") is None

    def test_text_only(self):
        assert parse_transaction("hello world") is None

    def test_just_a_number(self):
        assert parse_transaction("42") is None

    def test_command(self):
        assert parse_transaction("/void") is None

    def test_amount_after_to(self):
        assert parse_transaction("alice to 15") is None

    def test_negative_amount_string(self):
        # regex doesn't match negative
        assert parse_transaction("-10 to alice") is None

    def test_multiple_to_keywords(self):
        # "10 to alice to bob" – first "to" match, person = "alice to bob"
        result = parse_transaction("10 to alice to bob")
        assert result is not None
        assert result.person == "alice to bob"
