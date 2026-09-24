"""Utility module with no cryptographic operations."""

def process_data(items):
    results = []
    for item in items:
        results.append(item * 2)
    return results

class DataProcessor:
    def __init__(self, name):
        self.name = name

    def transform(self, data):
        return data.upper()

def calculate_sum(a, b):
    return a + b
