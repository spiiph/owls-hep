"""Provides method for efficiently histogramming properties of events in a
region.
"""

from __future__ import print_function

# System imports
from uuid import uuid4
from array import array

# Six imports
from six import string_types

# owls-parallel imports
from owls_parallel import parallelized

# owls-hep imports
from owls_hep.calculation import Calculation
from owls_hep.utility import make_selection, create_histogram, histogram, \
        integral, add_overflow_to_last_bin


# Set up default exports
__all__ = [
    'Histogram',
]

# Dummy function to return fake values when parallelizing
def _histogram_mocker(process, region, expressions, binnings):

    # Create a unique name for the histogram
    name = uuid4().hex

    # Create an empty histogram
    dimensionality = len(binnings)
    return create_histogram(dimensionality, name, binnings)

# Parallelization mapper batching in combinations of region, process, and
# expressions
def _histogram_mapper(process, region, expressions, binnings):
    return (process,region,expressions)

@parallelized(_histogram_mocker, _histogram_mapper)
def _histogram(process, region, expressions, binnings):
    """Wrapper around owls_hep.utility.histogram()

    Args:
        process: The process whose events should be histogrammed
        region: The region whose weighting/selection should be applied
        expressions: A tuple of expression strings
        binnings: A (tuple,list) of (tuples,lists) representing root binnings
        distribution: The distribution to histogram

    Returns:
        A ROOT histogram, of the TH1F, TH2F, or TH3F variety.
    """
    return histogram(process, region, expressions, binnings)

class Histogram(Calculation):
    """A histogramming calculation which generates a ROOT THN histogram.

    Although the need should not generally arise to subclass Histogram, all
    subclasses must return a ROOT THN subclass for their result.
    """

    def __init__(self, expressions, binnings, title, x_label, y_label,
                 include_overflow = False):
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
            include_overflow: Add contents of overflow bin to last bin
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
        self._include_overflow = include_overflow

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
        print_me = process.metadata().get('print_me', [])
        if [v for v in print_me
            if v in ['selection', 'expressions', 'counts']]:
            print('=== Process: {} ==='.format(process))

        # Compute the histogram
        result = _histogram(process, region, self._expressions, self._binnings)

        if 'selection' in print_me:
            print('Selection: {}'.format(make_selection(process, region)))
        if 'expressions' in print_me:
            print('Expressions: {}'.format(':'.join(self._expressions)))
        if 'counts' in print_me:
            print('Counts: {:.1f}'.format(integral(result)))

        if [v for v in print_me
            if v in ['selection', 'expressions', 'counts']]:
            print()

        # Set labels
        result.SetTitle(self._title)
        result.GetXaxis().SetTitle(self._x_label)
        result.GetYaxis().SetTitle(self._y_label)

        # Style the histogram
        process.style(result)

        # All done
        return result

    # TODO: Disabled for now; it's probably better to handle this in the
    # end user clients (e.g. plot.py etc)
    # def finalize_result(self, result):
        # """Method to polish the final histogram. Used to add overflow to last
        # bin, if desired.

        # Args:
            # result: The the final histogram
        # """

        # Add content of overflow bin to last bin
        # if self._include_overflow:
            # add_overflow_to_last_bin(result)


