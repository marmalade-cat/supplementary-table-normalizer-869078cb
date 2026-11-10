supplementary-table-normalizer

A minimal Python prototype CLI and library to discover CSV/TSV/JSON files in a local folder, normalize simple tabular/module data into a small JSON schema (poses, edges, sequences), validate basic required fields, and print a summary report.

Usage:

  python main.py /path/to/folder

This prototype intentionally keeps dependencies to the Python standard library and omits network fetching. It's a starting point for more advanced heuristics and URL support.

Schema (informal):
- poses: list of {id, x, y, z?, yaw?, pitch?, roll?}
- edges: list of {source, target, type?}
- sequences: list of {id, steps: [{time?, module?}]}

Limitations: lightweight and heuristic-based. See main.py for details and TODOs.