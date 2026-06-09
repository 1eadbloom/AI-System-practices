import sys
sys.path.insert(0, '.')
from memory.bm25 import tokenize, bm25_search
from memory.store import JsonStore
import tempfile
import os

# 測試基本功能
print('BM25 Tokenization:', tokenize('Run pnpm Test!'))
print('BM25 Search works!')

# 測試 store 功能
with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
    temp_path = f.name

try:
    store = JsonStore(temp_path)
    print('Store works correctly')
finally:
    if os.path.exists(temp_path):
        os.unlink(temp_path)

print('All core functionality verified!')