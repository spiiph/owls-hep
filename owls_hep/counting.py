"""Provides method for efficiently counting events in a region.
"""

# System imports
from uuid import uuid4

# ROOT imports
from ROOT import gDirectory

# owls-cache imports
from owls_cache.persistent import cached as persistently_cached

# owls-parallel imports
from owls_parallel import parallelized

# owls-hep imports
from owls_hep.calculation import Calculation
from owls_hep.expression import multiplied


@parallelized(lambda p, r: 1.0, lambda p, r: (p, r))
@persistently_cached('owls_hep.counting._count', lambda p, r: (p, r))
def _count(process, region):
    """Computes the weighted event count of a process in a region.

    Args:
        process: The process whose events should be counted
        region: The region whose weighting/selection should be applied

    Returns:
        The weighted event count in the region.
    """
    # Get the combined selection and weight from the region
    region_selection = region.selection_weight()

    # Get patches
    patches = process.patches()

    if not patches:
        selection = region_selection
    else:
        selection = multiplied(region_selection, patches)

    # Create a unique name and title for the histogram
    name = title = uuid4().hex

    # Create the expression string and specify which histogram to fill
    expression = '1>>{0}'.format(name)

    # Load the chain
    chain = process.load()
    chain.Draw(expression, selection)
    h = gDirectory.Get(name)
    return h.Integral(-1, h.GetNbinsX()+1)

class Count(Calculation):
    """A counting calculation.

    Although the need should not generally arise to subclass Count, all
    subclasses must return a floating point value for their result.
    """

    def __call__(self, process, region):
        """Counts the number of weighted events passing a region's selection.

        Args:
            process: The process whose weighted events should be counted
            region: The region providing selection/weighting for the count

        Returns:
            The number of weighted events passing the region's selection.
        """
        return _count(process, region)
