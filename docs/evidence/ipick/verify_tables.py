"""Verify portable peak-table evidence using only the Python standard library."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def read(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['files_sha256'].items():
        assert hashlib.sha256((directory/name).read_bytes()).hexdigest() == expected, name
    tables = read(directory/'table_comparison.csv')
    pairs = read(directory/'candidate_pairs.csv')
    matches = read(directory/'matching_comparison.csv')
    assert len(tables) == 24
    total = 0
    for t in tables:
        group = [p for p in pairs if p['index'] == t['index'] and p['level'] == t['level']]
        count = int(t['api_candidates'])
        assert count == int(t['ipick_candidates']) == int(t['unique_pairs']) == len(group)
        assert len({p['api_row'] for p in group}) == count
        assert len({p['ipick_row'] for p in group}) == count
        maxima = [0., 0.]
        for p in group:
            for i, axis in enumerate(['H', 'N']):
                difference = float(p['ipick_'+axis])-float(p['api_'+axis])
                assert abs(difference-float(p['delta_'+axis])) < 1e-12
                assert abs(difference) <= float(t['grid_step_'+axis])
                maxima[i] = max(maxima[i], abs(difference))
        assert abs(maxima[0]-float(t['max_abs_dH'])) < 1e-12
        assert abs(maxima[1]-float(t['max_abs_dN'])) < 1e-12
        total += count
    cells = sum(int(r['compared_cells']) for r in matches)
    different = sum(int(r['validity_disagreements']) for r in matches)
    disagreements = read(directory/'matching_disagreements.csv')
    assert total == 5175 and cells == 8088 and different == len(disagreements) == 4
    assert len({(r['context'], r['execution_id'], r['member']) for r in disagreements}) == 1
    print(f'Verified: {len(tables)} tables; {total} unique within-table pairs; '
          f'{cells-different}/{cells} availability flags agree; 1 member-run disagreement.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path, default=Path(__file__).resolve().parent)
    verify(parser.parse_args().directory)


if __name__ == '__main__':
    main()
