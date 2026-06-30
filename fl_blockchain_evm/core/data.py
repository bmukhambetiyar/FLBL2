"""Dataset dispatch — selects data loader based on FL_DATASET env var.

  FL_DATASET=ucihar  (default) → data_ucihar.py   (6 classes, 9 ch, 128-sample)
  FL_DATASET=pamap2             → data_pamap2.py   (12 classes, 27 ch, 512-sample)
  FL_DATASET=mhealth            → data_mhealth.py  (12 classes, 23 ch, 256-sample)
"""

import os as _os

_FL_DATASET = _os.getenv("FL_DATASET", "ucihar")

if _FL_DATASET == "pamap2":
    from fl_blockchain_evm.core.data_pamap2 import (  # noqa: F401
        load_data, compute_and_save_norm_stats, _balance_ros_rus, _augment,
    )
elif _FL_DATASET == "mhealth":
    from fl_blockchain_evm.core.data_mhealth import (  # noqa: F401
        load_data, compute_and_save_norm_stats, _balance_ros_rus, _augment,
    )
else:
    from fl_blockchain_evm.core.data_ucihar import (  # noqa: F401
        load_data, compute_and_save_norm_stats, _balance_ros_rus, _augment,
    )
