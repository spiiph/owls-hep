"""Provides method for efficiently histogramming properties of events in a
region.
"""

from __future__ import print_function

# System imports
from uuid import uuid4

# Six imports
from six import string_types

# ROOT imports
from ROOT import TH2F, TGraphAsymmErrors, TEfficiency

# owls-cache imports
from owls_cache.persistent import cached as persistently_cached

# owls-parallel imports
from owls_parallel import parallelized

# owls-hep imports
from owls_hep.calculation import Calculation
from owls_hep.utility import make_selection, histogram, integral, get_bins


# Set up default exports
__all__ = [
    'Efficiency',
]

# Dummy function to return fake values when parallelizing
def _efficiency_mocker(process, region, filter, expressions, binnings):
    dimensionality = len(binnings)
    if dimensionality == 1:
        return TGraphAsymmErrors()
    elif dimensionality == 2:
        return TH2F()
    else:
        raise RuntimeError('Can\'t create an efficiency mocker with more '
                           'than 2 dimensions.')

# Parallelization mapper batching in combinations of region and process
def _efficiency_mapper(process, region, filter, expressions, binnings):
    return (process,region)

def _make_consistent(passed, total):
    """Helper function to make the passed and total histograms consistent for
    histogram division/efficiency calculations.
    """
    # Include overflow bins
    for i in range(passed.GetNbinsX()+2):
        if total.GetBinContent(i) <= 0:
            total.SetBinContent(i, 1.0)
            passed.SetBinContent(i, 0.0)
        elif passed.GetBinContent(i) < 0:
            passed.SetBinContent(i, 0)
        elif total.GetBinContent(i) < passed.GetBinContent(i):
            passed.SetBinContent(i, total.GetBinContent(i))
            passed.SetBinError(i, total.GetBinError(i))

@parallelized(_efficiency_mocker, _efficiency_mapper)
@persistently_cached('owls_hep.efficiency._efficiency')
def _efficiency(process, region, filter, expressions, binnings):
    name = uuid4().hex

    # TODO: Consider storing the integral of the passed and total histograms
    # for use in the efficiency graph's title at a later point
    passed = histogram(process, region.varied(filter),
                       expressions, binnings)
    total = histogram(process, region,
                      expressions, binnings)

    if total.GetDimension() == 1:
        # Reset bin content for bins with 0 in the total to total = 1, passed
        # = 0. Due to negative weights and low stats some bins can have
        # passed > total; set the content for such bins to passed = total.
        _make_consistent(passed, total)
        rep = TGraphAsymmErrors(passed, total)

        #passed_bins = get_bins(passed, True)
        #total_bins = get_bins(total, True)
        #rep_bins = get_bins(rep)
        #if all([x == 0.0 for x,y in rep_bins]):
            #print('{0} {1}'.format(process._label, filter))
            #print(['{0:7.2f}'.format(y) for x,y in passed_bins])
            #print(['{0:7.2f}'.format(y) for x,y in total_bins])
            #print(['{0:7.2f}'.format(y) for x,y in rep_bins])
            #print(['({0:.0f}, {1:.2f})'.format(x, y) for x,y in rep_bins])
    else:
        rep = passed.Clone()
        rep.Divide(total)
    rep.SetName(name)
    return rep

class Efficiency(Calculation):
    """An efficiency calculation which generates a ROOT TGraphAsymmErrors or
    a TH2 histogram.
    """

    def __init__(self, expressions, binnings, title, x_label, y_label):
        """Initializes a new instance of the Efficiency calculation.

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

    def __call__(self, process, region, filter):
        """Histograms weighted events passing unfiltered and filtered
        variants of a region's selection into an efficiency plot.

        Args:
            process: The process whose weighted events should be histogrammed
            region: The region providing selection/weighting for the
                efficiency calculation
            filter: The filter to apply to the region for the efficiency
                calculation

        Returns:
            A TGraphAsymmErrors or TH2 histogram.
        """
        # Print some debug info
        #print('Selection: {0}'.format(make_selection(process, region)))
        #print('Expressions: {0}'.format(':'.join(self._expressions)))

        result = _efficiency(process, region, filter,
                             self._expressions, self._binnings)

        # Set labels
        result.SetTitle(self._title)
        result.GetXaxis().SetTitle(self._x_label)
        result.GetYaxis().SetTitle(self._y_label)

        # Style the histogram
        process.style(result)

        # All done
        return result
