"""Independent line and branch gates; rounded combined coverage is insufficient."""
import json
import sys
from pathlib import Path

totals=json.loads(Path(sys.argv[1]).read_text())['totals']
for label,covered,total in [('lines',totals['covered_lines'],totals['num_statements']),
                            ('branches',totals['covered_branches'],totals['num_branches'])]:
    if not total:raise SystemExit(f'{label}: no executable denominator')
    percentage=100*covered/total
    print(f'{label}: {percentage:.2f}% ({covered}/{total})')
    if percentage<90:raise SystemExit(f'{label}: below required 90%')
