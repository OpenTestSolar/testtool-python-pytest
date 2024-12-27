import allure
import pytest


@allure.step
def step_function_with_args(arg1, arg2):
    pass


@allure.step("Step with param '{param}'")
def step_with_placeholder(param):
    pass


@allure.step("Custom step title")
def step_function_with_title():
    pass

test_data = [
    {"repo_name": "repo1", "action": "create"}
]
@pytest.mark.parametrize("data", test_data)
def test_step(data):
    print(f"{data['action'].capitalize()}测试仓库 {data['repo_name']}")
    with allure.step("First step"):
        step_with_placeholder("Param value")
        with allure.step("Nested step"):
            step_function_with_args("value1", "value2")
    step_function_with_title()
