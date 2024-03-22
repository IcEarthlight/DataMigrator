def parse(script: str | list | dict[str: ...], indent: int = 0) -> str:
    """ Parse and return python script in a json format into normal string. """

    if isinstance(script, str):
        return ' ' * 4*indent + script + '\n'
    
    elif isinstance(script, list):
        s: str = ''
        for code in script:
            s += parse(code, indent)
        return s
    
    elif isinstance(script, dict):
        s: str = ''
        for k, v in script.items():
            s += parse(k + ':', indent)
            s += parse(v, indent + 1)
        return s
