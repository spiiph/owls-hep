"""Provides method for efficiently histogramming properties of events in a
region.
"""

from __future__ import print_function

# System imports
from uuid import uuid4
from array import array

# Six imports
from six import string_types

# ROOT imports
from ROOT import TH1F, TH2F, TH3F

# owls-cache imports
from owls_cache.persistent import cached as persistently_cached

# owls-parallel imports
from owls_parallel import parallelized

# owls-hep imports
from owls_hep.calculation import Calculation
from owls_hep.expression import multiplied



# Set up default exports
__all__ = [
    'Histogram',
]

# NOTE: This function takes binnings of the form (nbins, low, up) or (low1,
# low2, low3, ..., lowN, upN). We could reinstate the type as the first
# element of the tuple, but to what end?
def _rootify_binning(*args):
    if len(args) < 3:
        raise ValueError('Need at least three values to create a proper binning')
    if len(args) == 3:
        return tuple(args)
    else:
        return (len(args)-1, array('f', args))

def _create_histogram(dimensionality, name, binnings):
    # Create the bare histogram
    if dimensionality == 1:
        return TH1F(name, name, *_rootify_binning(*binnings[0]))
    elif dimensionality == 2:
        flat_binnings = \
                _rootify_binning(*binnings[0]) + \
                _rootify_binning(*binnings[1])
        return TH2F(name, name, *flat_binnings)
    elif dimensionality == 3:
        flat_binnings = \
                _rootify_binning(*binnings[0]) + \
                _rootify_binning(*binnings[1]) + \
                _rootify_binning(*binnings[2])
        return TH3F(name, name, *flat_binnings)
    else:
        raise ValueError('ROOT can only histograms 1 - 3 dimensions')

# Dummy function to return fake values when parallelizing
def _parallel_mocker(process, region, expressions, binnings):

    # Create a unique name and title for the histogram
    name = title = uuid4().hex

    # Create an empty histogram
    # NOTE: When specifying explicit bin edges, you aren't passing a length
    # argument, you are passing an nbins argument, which is length - 1, hence
    # the code below.  If you pass length for n bins, then you'll get garbage
    # for the last bin's upper edge and things go nuts in ROOT.
    dimensionality = len(binnings)
    return _create_histogram(dimensionality, name, binnings)

# Histogram parallelization mapper.  We map/group based on process to maximize
# data loading caching.
# NOTE: Changed parallelizatoin to map on expressions instead.
def _parallel_mapper(process, region, expressions, binnings):
    return (process,)
    #return (expressions,)

# Histogram parallelization batcher
def _parallel_batcher(function, args_kwargs):
    # Go through all args/kwargs pairs and call the function
    for args, kwargs in args_kwargs:
        # Call the functions
        function(*args, **kwargs)

def _make_selection(process, region):
    # Get the combined selection and weight from the region
    region_selection = region.selection_weight()

    # Get patches
    patches = process.patches()

    # Construct the final selection from the region selection and weight and
    # the processes patches.
    if not patches:
        selection = region_selection
    else:
        selection = multiplied(region_selection, patches)
    return selection


@parallelized(_parallel_mocker, _parallel_mapper, _parallel_batcher)
@persistently_cached('owls_hep.histogramming._histogram')
def _histogram(process, region, expressions, binnings):
    """Generates a ROOT histogram of a distribution a process in a region.

    Args:
        process: The process whose events should be histogrammed
        region: The region whose weighting/selection should be applied
        expressions: A tuple of expression strings
        binnings: A (tuple,list) of (tuples,lists) representing root binnings
        distribution: The distribution to histogram

    Returns:
        A ROOT histogram, of the TH1F, TH2F, or TH3F variety.
    """
    # Create a unique name and title for the histogram
    name = title = uuid4().hex

    # Create the selection
    selection = _make_selection(process, region)

    # Create the expression string and specify which histogram to fill
    expression = ' : '.join(expressions) + '>>{0}'.format(name)

    # Create the bare histogram
    dimensionality = len(expressions)
    h = _create_histogram(dimensionality, name, binnings)

    # Load the chain
    chain = process.load()
    chain.Draw(expression, selection)
    return h


class Histogram(Calculation):
    """A histogramming calculation which generates a ROOT THN histogram.

    Although the need should not generally arise to subclass Histogram, all
    subclasses must return a ROOT THN subclass for their result.
    """

    def __init__(self, expressions, binnings, title, x_label, y_label):
        """Initializes a new instance of the Histogram calculation.

        Args:
            expressions: The expression (as a string or 1-tuple of a string) or
                expressions (as an N-tuple of strings), in terms of dataset
                variables, to histogram.  The multiplicity of expressions
                determines the dimensionality of the histogram.
            binnings: The binning (as a tuple or a 1-tuple of tuples) or
                binnings (as an N-tuple of tuples). The binning count must
                match the expression count.
            title: The ROOT TLatex label to use for the histogram title
            x_label: The ROOT TLatex label to use for the x-axis
            y_label: The ROOT TLatex label to use for the y-axis
        """
        # Store parameters
        if isinstance(expressions, string_types):
            self._expressions = (expressions,)
        else:
            self._expressions = expressions
        if isinstance(binnings[0], tuple):
            self._binnings = binnings
        else:
            self._binnings = (binnings,)
        self._title = title
        self._x_label = x_label
        self._y_label = y_label

        # Validate that expression and binning counts jive
        if len(self._expressions) != len(self._binnings):
            raise ValueError('histogram bin specifications must have the same '
                             'length as expression specifications')

    def title(self):
        """Returns the title for this histogram calculation.
        """
        return self._title

    def x_label(self):
        """Returns the x-axis label for this histogram calculation.
        """
        return self._x_label

    def y_label(self):
        """Returns the y-axis label for this histogram calculation.
        """
        return self._y_label

    def __call__(self, process, region):
        """Histograms weighted events passing a region's selection into a
        distribution.

        Args:
            process: The process whose weighted events should be histogrammed
            region: The region providing selection/weighting for the histogram

        Returns:
            A ROOT histogram representing the resultant distribution.
        """
        # Print some debug info
        #print('Selection: {0}'.format(_make_selection(process, region)))
        #print('Expressions: {0}'.format(':'.join(self._expressions)))
        # Compute the histogram
        result = _histogram(process, region, self._expressions, self._binnings)

        # Set labels
        result.SetTitle(self._title)
        result.GetXaxis().SetTitle(self._x_label)
        result.GetYaxis().SetTitle(self._y_label)

        # Style the histogram
        process.style(result)

        # All done
        return result


def integral(hist, include_overflow = True):
    """A helper function to compute the integral for THN histograms of
    dimensionality D <= 3.
    """
    offset = 1 if include_overflow else 0
    if hist.GetDimension() == 1:
        return hist.Integral(1-offset, hist.GetNbinsX()+offset)
    elif hist.GetDimension() == 2:
        return hist.Integral(1-offset, hist.GetNbinsX()+offset,
                             1-offset, hist.GetNbinsY()+offset)
    elif hist.GetDimension() == 3:
        return hist.Integral(1-offset, hist.GetNbinsX()+offset,
                             1-offset, hist.GetNbinsY()+offset,
                             1-offset, hist.GetNbinsZ()+offset)
    else:
        raise ValueError('don''t know how to compute the integral for '
                         'more than 3 dimensions')

