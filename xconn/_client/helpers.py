import inspect
import json
from typing import get_type_hints

from pydantic import BaseModel

from xconn.exception import ApplicationError
from xconn.types import Event, Invocation, Result


def is_primitive(obj) -> bool:
    return isinstance(obj, (str, int, float, bool, bytes, type(None)))


def _validate_procedure_function(func: callable, uri: str):
    sig = inspect.signature(func)
    for name, param in sig.parameters.items():
        if param.annotation is inspect._empty:
            raise RuntimeError(f"Missing type hint for parameter: '{name}' in function '{func.__name__}'")

    hints = get_type_hints(func)
    hints.pop("return") if "return" in hints else None

    if Invocation in hints.values():
        if len(hints) != 1:
            raise RuntimeError(f"Cannot use other types than 'Invocation' as arguments in procedure '{uri}'")

    pydantic_model = None
    positional_args = []
    for type_ in hints.values():
        if issubclass(type_, BaseModel):
            if len(hints) != 1:
                raise RuntimeError(f"Cannot mix pydantic dataclass with other types in signature of procedure '{uri}'")

            pydantic_model = type_

            for key, value in pydantic_model.model_fields.items():
                if value.is_required:
                    positional_args.append(key)

    response_model = func.__xconn_response_model__
    response_positional_args = []
    if response_model is not None:
        for key, value in response_model.model_fields.items():
            if value.is_required:
                response_positional_args.append(key)

    return pydantic_model, response_model, positional_args, response_positional_args


def _handle_result(
    result: Result | tuple | None,
    response_model: type[BaseModel] | None,
    response_positional_args: list[str],
) -> Result:
    if result is None:
        if response_model is not None:
            raise ApplicationError(
                "wamp.error.internal_error", "Procedure returned None, but a response model was provided."
            )

        return Result()

    if isinstance(result, Result):
        if response_model is None:
            return result

        response_args = result.args if result.args is not None else []
        response_kwargs = result.kwargs if result.kwargs is not None else {}

        # If the Result object was returned, we need to be able to map
        # its args to their keys so that the pydantic model can be initialized.
        if len(response_args) != len(response_positional_args):
            raise ApplicationError("wamp.error.internal_error")

        args_with_keys = dict(zip(response_positional_args, response_args))

        # FIXME: catch ValidationError and return ApplicationError
        args = response_model(**args_with_keys, **response_kwargs)
        return Result(args=[args.model_dump()])

    if response_model is None:
        # No response model provided, return the result as-is.
        # We avoid validating the data and shift the responsibility
        # to the serializer.
        return Result(args=[result])

    if is_primitive(result):
        if len(response_positional_args) != 1:
            raise ApplicationError(
                "wamp.error.internal_error",
                f"Procedure returned a single primitive but response model has {len(response_positional_args)} positional args.",
            )

        # FIXME: catch ValidationError and return ApplicationError
        args = response_model(**{response_positional_args[0]: result})
        return Result(args=[args.model_dump()])

    # If the result is a tuple, it usually means a python function returned multiple values.
    # Though that might not always be the case, and a function may explicitly return a tuple as well.
    if isinstance(result, tuple):
        if len(result) != len(response_positional_args):
            raise ApplicationError(
                "wamp.error.internal_error",
                f"Procedure returned {len(result)} values but the response model has {len(response_positional_args)} args.",
            )

        args_with_keys = dict(zip(response_positional_args, result))

        # FIXME: catch ValidationError and return ApplicationError
        args = response_model(**args_with_keys)
        return Result(args=[args.model_dump()])

    if isinstance(result, list):
        # FIXME: catch ValidationError and return ApplicationError
        return Result(args=[json.loads(response_model.from_orm(item).json()) for item in result])

    # FIXME: catch ValidationError and return ApplicationError
    return Result(args=[json.loads(response_model.from_orm(result).json())])


def _validate_topic_function(func: callable, uri: str):
    sig = inspect.signature(func)
    for name, param in sig.parameters.items():
        if param.annotation is inspect._empty:
            raise RuntimeError(f"Missing type hint for parameter: '{name}' in function '{func.__name__}'")

    hints = get_type_hints(func)
    hints.pop("return") if "return" in hints else None

    if Event in hints.values():
        if len(hints) != 1:
            raise RuntimeError(f"Cannot use other types than 'Event' as arguments in subscription '{uri}'")

    pydantic_model = None
    positional_args = []
    for type_ in hints.values():
        if issubclass(type_, BaseModel):
            if len(hints) != 1:
                raise RuntimeError(
                    f"Cannot mix pydantic dataclass with other types in signature of subscription '{uri}'"
                )

            pydantic_model = type_

            for key, value in pydantic_model.model_fields.items():
                if value.is_required:
                    positional_args.append(key)

    return pydantic_model, positional_args
