"""Behaviour-level declaration (**a pure data module**, excluded from ``behavior_digest``).

After changing ``core/`` / ``backend/`` / ``workflow/`` / ``nmrfinesse_api/`` or the shipped
data (``config/nmrfinesse.yaml``, ``presets/``), ``tests/test_compat.py``'s
``test_behavior_digest_matches_the_declaration`` fails -- update in this order:

1. **Decide the level**: ``same`` (comments/wording or docstrings only) / ``additive`` (new
   entry points or optional fields only, downstream need not re-run) / ``behavior_changed``
   (**numbers change**) / ``contract_changed`` (columns/fields/error codes changed);
2. ``behavior_changed`` / ``contract_changed`` must name ``affected`` (values in
   ``nmrfinesse_api.compat.AFFECTED_STEPS``); downstream uses it to decide what to re-run;
3. **Recompute the fingerprints**: copy ``behavior_digest`` / ``token_digest`` from
   ``python -m nmrfinesse_api compat --out compat.json`` back into this file;
4. **Golden vector**: when behaviour or recipes change, sync the ``golden`` hashes
   (``python -m nmrfinesse_api compat --golden`` prints the actual values);
5. ``compat_level=same`` requires ``token_digest`` to be unchanged (proof that the code
   tokens did not move and only comments/docstrings did).
"""

from __future__ import annotations

from typing import Any

#: declared behaviour level (see the module doc; meaning matches nmrfinesse_api.compat)
DECLARATION: dict[str, Any] = {'schema': 'nmrfinesse_api.compat.declaration.v1',
 'digest': '5eab4e9e5a80e9b89f3e09ad6bc8faedc84f631021d525a7412daa91952cfd11',
 'token_digest': '62c4a46520a3a9be6e0095b994a15bcb4f37716fd3a7975149dbbe6f1489bb7d',
 'compat_level': 'additive',
 'affected': [],
 'updated': '2026-10-29',
 'note': 'Add coordinate-only peak export; retain internal metrics and detection '
         'numerics.',
 'golden': {'name': 'conformance_v1',
            'spectrum_sha256': '382b330926da93d856feef40ca33c2df1eec21b61e50db471bdf7aa4bb2fb311',
            'peak_table_sha256': 'e9ef45f2cae32bc580fc1bdeea1928ceb8406154848f8aca3c4558285e532242',
            'n_peaks': 3}}

__all__ = ["DECLARATION"]
