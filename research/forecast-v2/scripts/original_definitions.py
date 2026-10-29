"""Print SHA-256 of every top-level definition of the released modules (for the preservation test).

Usage: git show Main:forecast/wildfire/train.py | python original_definitions.py
"""
import ast
import hashlib
import json
import sys

source = sys.stdin.read()
tree = ast.parse(source)
result = {}
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
        segment = ast.get_source_segment(source, node)
        result[node.name] = hashlib.sha256(segment.encode()).hexdigest()
print(json.dumps(dict(bytes=len(source.encode()), sha256=hashlib.sha256(source.encode()).hexdigest(),
                      definitions=result), indent=1))
