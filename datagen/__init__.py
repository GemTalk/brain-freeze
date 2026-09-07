"""The dataset generator. Not part of the demo -- an internal tool.

This package exists to keep a boundary visible that a docstring could only
assert. `brainfreeze/` is standard-library only, because it is imported and
compiled *inside* the database, where numpy and pandas do not exist. This
package is the only thing in the repo allowed to import them, and it does the
sampling: how many policyholders, how their answers are drawn, how much noise
sits on a premium, the small chance of a denial for a reason the rules do not
model.

Every deterministic decision -- what a policy is scored, what it costs, what a
claim pays -- is delegated to `brainfreeze`. That split is what stops the app's
quote and the sample data from drifting into disagreement, and
`test_brainfreeze.py` exists to catch it if they ever do.

    python3 -m datagen        # rewrites policyholders.csv and claims.csv

The output is byte-identical run to run. If it stops being, either something
is wrong or the dataset is being regenerated deliberately -- and if it is the
latter, say so loudly: every figure in `mockups/` and every number in the tests
is read out of these two files.
"""

from .dataset import main, make_claims, make_policyholders

__all__ = ["main", "make_claims", "make_policyholders"]
