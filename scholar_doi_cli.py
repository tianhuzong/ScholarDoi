"""scholar-doi 命令行入口脚本(便于直接运行)。

用法:
    python scholar_doi_cli.py doi 10.1000/xyz -o ./papers -e you@example.com
"""
import sys
from scholar_doi.cli import main

if __name__ == "__main__":
    sys.exit(main())