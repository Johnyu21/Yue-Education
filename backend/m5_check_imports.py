"""Check M5 imports and imported symbols without calling business APIs or databases.
Run from the project root with backend/.venv/Scripts/python.exe backend/m5_check_imports.py.
Python automatically uses this script's backend directory as the import root.
"""
import ast
import importlib
import inspect
import json
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parent

def check_imports():
    files = sorted((BACKEND / 'app').rglob('m5_*.py'))
    failures = []
    checked = []
    for path in files:
        tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            namespace = {}
            statement = ast.unparse(node)
            try:
                exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
                for alias in node.names:
                    name = alias.asname or (alias.name.split('.')[0] if isinstance(node, ast.Import) else alias.name)
                    obj = namespace[name]
                    module_name = obj.__name__ if inspect.ismodule(obj) else (node.module if isinstance(node, ast.ImportFrom) else getattr(obj, '__module__', ''))
                    module = importlib.import_module(module_name) if module_name else None
                    origin = getattr(module, '__file__', None)
                    imported_module = node.module if isinstance(node, ast.ImportFrom) else alias.name
                    if imported_module == 'app' or imported_module.startswith('app.'):
                        if not origin or not Path(origin).resolve().is_relative_to((BACKEND/'app').resolve()):
                            raise ImportError('Project import resolved outside this backend: ' + str(origin))
                    checked.append({'source':str(path.relative_to(BACKEND)), 'line':node.lineno,
                                    'import':statement, 'symbol':alias.name, 'target':str(origin) if origin else 'builtin'})
            except Exception as exc:
                failures.append({'source':str(path.relative_to(BACKEND)), 'line':node.lineno,
                                 'import':statement, 'error_type':type(exc).__name__})
    return {'interpreter':sys.executable, 'files':len(files), 'symbols':len(checked),
            'failures':failures, 'imports':checked}

if __name__ == '__main__':
    result=check_imports()
    if '--json' in sys.argv:
        print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        print('M5 files:',result['files'])
        print('Imported symbols:',result['symbols'])
        print('Import failures:',len(result['failures']))
        for failure in result['failures']:
            print(failure['source'],failure['line'],failure['import'],failure['error_type'])
    raise SystemExit(1 if result['failures'] else 0)
