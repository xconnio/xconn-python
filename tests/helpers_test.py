import pytest
from pydantic import ValidationError

from xconn.helpers import validate_data


def valid_handler(a: int, b: str, c: float = 0.0):
    return a + len(b) + c


def test_validate_data_with_valid_handler():
    validated_handler = validate_data(valid_handler)
    assert callable(validated_handler)

    # Test with valid inputs
    result = validated_handler(10, "hello", 1.5)
    assert result == 16.5

    # Test with default value for 'c'
    result = validated_handler(10, "hi")
    assert result == 12.0


def test_validate_data_with_missing_annotations():
    def missing_annotation_handler(a, b: str):
        return a + len(b)

    with pytest.raises(TypeError, match="Parameter 'a' is missing a type annotation."):
        validate_data(missing_annotation_handler)


def test_validate_data_with_mismatched_types():
    validated_handler = validate_data(valid_handler)
    with pytest.raises(ValidationError):
        validated_handler("not_an_int", "hello", 1.5)

    with pytest.raises(ValidationError):
        validated_handler(10, 12345, 1.5)


def test_validate_data_with_missing_required_args():
    validated_handler = validate_data(valid_handler)
    with pytest.raises(ValidationError):
        validated_handler(10)


def test_validate_data_with_extra_args():
    validated_handler = validate_data(valid_handler)
    with pytest.raises(ValidationError):
        validated_handler(10, "hello", 1.5, "extra_arg")


def test_validate_data_with_valid_kwargs():
    validated_handler = validate_data(valid_handler)
    result = validated_handler(a=10, b="hello", c=1.5)
    assert result == 16.5

    # Test with default value for 'c'
    result = validated_handler(a=10, b="hi")
    assert result == 12.0


def test_validate_data_with_invalid_kwargs():
    validated_handler = validate_data(valid_handler)
    with pytest.raises(ValidationError):
        validated_handler(a=10, b="hello", d=1.5)
