"""Names used in a module that are neither bound there nor builtins."""
import ast, builtins, sys
from pathlib import Path

def scan(path):
    src = Path(path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    bound = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.Global):
            bound.update(node.names)
    used = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.setdefault(node.id, node.lineno)
    out = {}
    for name, line in sorted(used.items(), key=lambda kv: kv[1]):
        if name not in bound:
            out.setdefault(name, line)
    return out

for p in sys.argv[1:]:
    r = scan(p)
    print("==", p, len(r), "unresolved")
    for k, v in r.items():
        print("   %-22s line %d" % (k, v))
