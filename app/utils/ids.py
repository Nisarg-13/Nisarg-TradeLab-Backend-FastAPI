from cuid2 import cuid_wrapper

_generate_cuid = cuid_wrapper()


def generate_cuid() -> str:
    return _generate_cuid()
