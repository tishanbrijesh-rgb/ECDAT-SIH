"""Demonstrates shadowed imports — the imported names are not used for crypto."""


def process() -> None:
    # Local binding shadows the module-level import
    hashlib = "not_a_module"
    hmac = 42
    print(hashlib, hmac)
    return None

class Parser:
    def __init__(self):
        # Instance attribute shadows module import
        self.hashlib = {}
        self.hmac = []
