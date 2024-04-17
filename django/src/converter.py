def selector_to_django(test_selector: str) -> str:
    """
    translate from test selector format to django format
    """
    if test_selector.endswith("/"):
        test_selector = test_selector[:-1]
    if "?" in test_selector:
        module, name = test_selector.split("?", 1)
    else:
        module, name = test_selector, ""
    if module.endswith(".py"):
        module = module[:-3]
    module = module.replace("/", ".")
    if name:
        return module + "." + name
    else:
        return module
