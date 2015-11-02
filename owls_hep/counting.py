"""Provides method for efficiently counting events in a region.
"""

# System imports
from uuid import uuid4

# owls-cache imports
from owls_cache.persistent import cached as persistently_cached

# owls-parallel imports
from owls_parallel import parallelized

# owls-hep imports
from owls_hep.calculation import Calculation
from owls_hep.utility import make_selection, integral, create_histogram

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
    # Create a unique name for the histogram
    name = uuid4().hex

    # Create the selection
    selection = make_selection(process, region)

    # Create the expression string and specify which histogram to fill
    expression = '1>>{0}'.format(name)

    # Create the bare histogram
    h = create_histogram(1, name, ((1, 0.5, 1.5),))

    # Load the chain
    chain = process.load()
    chain.Draw(expression, selection)

    # Return the count as the integral of the histogram, including overflow
    # bins
    return integral(h, include_overflow=True)

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
