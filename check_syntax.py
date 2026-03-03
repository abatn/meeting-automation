import os, ast, sys
has_error = False
for root, _, files in os.walk('backend/app'):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                code = f.read()
            try:
                ast.parse(code)
            except SyntaxError as e:
                print(f"SyntaxError in {path}: {e}")
                has_error = True
sys.exit(1 if has_error else 0)
