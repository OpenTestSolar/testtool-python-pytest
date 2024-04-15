import pathlib
from typing import Tuple, List

from testsolar_testtool_sdk.model.load import LoadError


def filter_invalid_selector_path(
    workspace: str, selectors: List[str]
) -> Tuple[List[str], List[LoadError]]:
    valid_selectors = []
    invalid_selectors = []
    for selector in selectors:
        path, _, _ = selector.partition("?")

        full_path = pathlib.Path(workspace, path).resolve()
        if not full_path.exists():
            message = f"[WARNING]Path {full_path} does not exist, SKIP it"
            print(message)
            invalid_selectors.append(
                LoadError(name=f"invalid selector [{selector}]", message=message)
            )
        else:
            valid_selectors.append(selector)

    return valid_selectors, invalid_selectors
