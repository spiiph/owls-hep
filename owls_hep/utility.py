"""Provides utility methods for processes, regions, expressions, and
calculations.
"""

# System imports
from uuid import uuid4
from array import array

# ROOT imports
from ROOT import TH1, TH1F, TH2F, TH3F, TGraph, Double, SetOwnership, \
        TGraphAsymmErrors

# owls-cache imports
from owls_cache.persistent import cached as persistently_cached

# owls-hep imports
from owls_hep.expression import multiplied

def get_bins(binned, include_overflow = False):
    """Get a list of bin content and bin centers of a TH1 or TGraph.

    Args:
        binned: The TH1 or TGraph object

    Returns:
        A list of (x, y) values
    """
    points = []
    if isinstance(binned, TGraph):
        x = Double()
        y = Double()
        for i in range(binned.GetN()):
            binned.GetPoint(i, x, y)
            points.append((float(x), float(y)))
    elif isinstance(binned, TH1):
        offset = 1 if include_overflow else 0
        points = [(binned.GetBinCenter(i+1), binned.GetBinContent(i+1))
                   for i in range(0-offset, binned.GetNbinsX()+offset)]
    else:
        raise RuntimeError('Unsupported object: {0}'.format(type(binned)))
    return points

def make_selection(process, region):
    """Make a selection string out of the selection and weight of a region
    and the patches of a process.

    Args:
        region: The region object
        process: The process object

    Returns:
        A selection string
    """
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


def integral(obj, include_overflow = True):
    """A helper function to compute the integral for THN histograms of
    dimensionality D <= 3.
    """
    offset = 1 if include_overflow else 0
    if obj.GetDimension() == 1:
        return obj.Integral(1-offset, obj.GetNbinsX()+offset)
    elif obj.GetDimension() == 2:
        return obj.Integral(1-offset, obj.GetNbinsX()+offset,
                             1-offset, obj.GetNbinsY()+offset)
    elif obj.GetDimension() == 3:
        return obj.Integral(1-offset, obj.GetNbinsX()+offset,
                             1-offset, obj.GetNbinsY()+offset,
                             1-offset, obj.GetNbinsZ()+offset)
    else:
        raise ValueError('don''t know how to compute the integral for '
                         'more than 3 dimensions')

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

def create_histogram(dimensionality, name, binnings):
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

@persistently_cached('owls_hep.histogramming._histogram')
def histogram(process, region, expressions, binnings):
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
    # Create a unique name for the histogram
    name = uuid4().hex

    # Create the selection
    selection = make_selection(process, region)

    # Create the expression string and specify which histogram to fill
    expression = ' : '.join(expressions) + '>>{0}'.format(name)

    # Create the bare histogram
    dimensionality = len(expressions)
    h = create_histogram(dimensionality, name, binnings)

    # Load the chain
    chain = process.load()
    chain.Draw(expression, selection)
    return h


def add_histograms(histograms):
    """Adds histograms and returns the result with bin errors calculated.

    Args:
        histograms: An iterable of histograms

    Returns:
        A histogram representing the sum of the input histograms, with bin
        errors calculated.
    """
    # Grab the first histogram, making sure bin errors are calculated before
    # adding the remaining histograms
    result = histograms[0].Clone(uuid4().hex)
    SetOwnership(result, False)
    if result.GetSumw2N() == 0:
        result.Sumw2()

    # Add the other histograms to the result
    map(result.Add, histograms[1:])

    return result

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

def efficiency(total, passed):
    name = uuid4().hex
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
        rep = passed.Clone(name)
        rep.Divide(total)
    rep.SetName(name)
    return rep

