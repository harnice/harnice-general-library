# harnice-general-library

NEMA WD-6 cord connectors, UL portable power cable, and generic ring terminals
for [Harnice](https://github.com/harnice/Harnice).

Each family is two files: a chooser that harness scripts import, and a
generator that writes SKUs. Do not import the generator from a harness.

| Family | Chooser | Generator | SKUs |
| --- | --- | --- | --- |
| NEMA WD-6 plugs / cord connectors | `connectors/nema_plugs/nema_plugs.py` | `nema_plugs_generator.py` | 114 |
| Portable power cable | `cables/portable_power_cable/portable_power_cable.py` | `portable_power_cable_generator.py` | 322 |
| Generic ring terminals | `parts/generic_ring_terminals/ring_terminal.py` | `ring_terminal_generator.py` | 150 |

Part origin is the cable-side face; `+X` runs toward the mating face.
`csys_children["3d-mate"]` sits on that face (blade tips on a NEMA plug,
ring tip on a terminal).

Regenerate every family:

```bash
python generate_all_in_repo.py
```

One family, drawings and STEP only:

```bash
python connectors/nema_plugs/nema_plugs_generator.py --no-build
```

Chooser import (today):

```python
import os
import sys
from harnice.utils import library_utils

LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
LIBRARY_SUBPATH = "connectors/nema_plugs"
sys.path.append(
    os.path.join(library_utils.get_local_path(LIBRARY_REPO), LIBRARY_SUBPATH)
)
import nema_plugs

nema_plugs.choose_part("5-15", "P")
nema_plugs.find_mating_connector("NEMA-L14-30P")
```
