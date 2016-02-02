"""Provides minor abstractions on top of ROOT to faciliate somewhat more
elegant plotting.  As with anything that interfaces with ROOT, there are
bound to be... idiosyncrasies, though this module does its best to hide them.
It provides several functions for manipulating histograms or collections
thereof:

    - drawable_iterable
    - combined_histogram
    - maximum_value
    - ratio_histogram
    - histogram_stack

It also provides a class, 'Plot', which can be used to model a ROOT plot,
enabling the following features:

    - Stacked background histograms
    - Data histograms
    - Legend
    - Ratio histograms
    - Statistical error bars
    - Systematic error bars

For more documentation, please see the docstrings for the individual functions
and/or Plot methods.
"""


# System imports
from math import ceil, sqrt
from uuid import uuid4
from itertools import chain

# Six imports
from six.moves import range
from six import string_types

# owls-hep imports
from owls_hep.utility import add_histograms, clone

# ROOT imports
# HACK: We import and use SetOwnership because ROOT's memory management is so
# inconsistent and terrible that we have to stop Python from even touching ROOT
# graphical objects or ROOT will crash, often due to a double free or some
# other nonsense.
from ROOT import TCanvas, TPad, TH1, TH2, THStack, TGraph, TMath, TF1, \
        TLegend, TLine, TLatex, TPaveText, TPaveLabel, TColor, SetOwnership, \
        gStyle

# Use Dark radiator color map for 2D COLZ plots
gStyle.SetPalette(53)

# Turn off stat box by default
gStyle.SetOptStat(0)

# Turn off the title
gStyle.SetOptTitle(0)


# Convenience function for generating random IDs
def _rand_uuid():
    return uuid4().hex


# Convenience function to check if an object is a TH1
def is_histo(h):
    return isinstance(h, TH1)

# Convenience function to check if an object is a TH2
def is_scatter(h):
    return isinstance(h, TH2)

# Convenience function to check if an object is a THStack
def is_stack(h):
    return isinstance(h, THStack)

# Convenience function to check if an object is a TGraph
def is_graph(g):
    return isinstance(g, TGraph)

# Convenience function to check if an object is a TLine
def is_line(l):
    return isinstance(l, TLine)

# Convenience function to check if an object is a TF1
def is_function(f):
    return isinstance(f, TF1)


def enable_stat(enable = True):
    if enable:
        gStyle.SetOptStat(1111)
    else:
        gStyle.SetOptStat(0)

def enable_fit(enable = True):
    if enable:
        gStyle.SetOptFit(1111)
    else:
        gStyle.SetOptFit(0)

def style_histogram(drawable, line_color, fill_color, marker_style,
                    line_size = 2):
    """Applies a style to a drawable object.

    Args:
        drawable: The object to style
        line_color, fill_color, marker_style: The style to apply
    """

    # Translate hex colors if necessary
    if isinstance(line_color, string_types):
        line_color = TColor.GetColor(line_color)
    if isinstance(fill_color, string_types):
        fill_color = TColor.GetColor(fill_color)

    # Set line color and width
    drawable.SetLineColor(line_color)
    drawable.SetLineWidth(line_size)

    # Set fill style and color
    drawable.SetFillStyle(1001)
    drawable.SetFillColor(fill_color)

    # Set marker style
    if marker_style is not None:
        drawable.SetMarkerStyle(marker_style)
        drawable.SetMarkerSize(2)
        drawable.SetMarkerColor(line_color)
    else:
        # HACK: Set marker style to an invalid value if not specified,
        # because we need some way to differentiate rendering in the legend
        drawable.SetMarkerStyle(0)

def style_line(drawable, line_color, line_style, line_size = 1):
    """Applies a style to a drawable with TAttLine capabilities.

    Args:
        drawable: The object to style
        line_color, line_style, line_size: The style to apply
    """

    # Translate hex colors if necessary
    if isinstance(line_color, string_types):
        line_color = TColor.GetColor(line_color)

    # Set line style, color, and width
    drawable.SetLineColor(line_color)
    drawable.SetLineStyle(line_style)
    drawable.SetLineWidth(line_size)

def drawable_iterable(drawable, unpack_stacks = False, reverse_stacks = False):
    """Convenience method to get an iterable object from a drawable.

    Args:
        drawable: Some type of drawable object.  Existing iterables are passed
            through.
        unpack_stacks: By default, THStack objects are treated as a single
            histogram.  If you would like them to be treated as a collection of
            their constituent TH1 objects, set unpack_stacks = True.
        reverse_stacks: If unpacking stacks, they are typically iterated from
            bottom to top.  Specify True for reverse_stacks to iterate from top
            to bottom.

    Returns:
        An iterable of the histograms in the provided collection.
    """
    # Check if we are using a THStack
    if is_stack(drawable) and unpack_stacks:
        # Extract histograms from the stack
        result = list(drawable.GetHists())

        # Reverse if necessary
        if reverse_stacks:
            result.reverse()

        return result
    elif is_histo(drawable) or is_graph(drawable) or is_line(drawable) \
            or is_function(drawable):
        return (drawable,)

    # Already an iterable
    return drawable


def combined_histogram(histograms_or_stack):
    """Returns a combined TH1 object from a collection of histograms with bin
    errors calculated.

    Args:
        histograms_or_stack: A single histogram, a non-empty iterable of
            histograms, or a THStack object which represents the collection of
            histograms

    Returns:
        A single TH1 object which is a combination of the provided histograms
        and which has bin errors calculated.
    """
    # Convert the histograms to an iterable, always unpacking THStack objects
    histograms = drawable_iterable(histograms_or_stack, True)
    result = add_histograms(histograms)

    return result


def maximum_value(drawables):
    """Returns the maximum value of all bins of all histograms or graphs
    provided, including any errors.

    Args:
        drawables: An iterable of drawable objects, each of one of the
            following types:

            - A TH1 object
            - A THStack object
            - A tuple of the form (THStack, TGraph) where the latter
              represents error bars
            - A TGraph object

    Returns:
        The maximum value than any bin takes on in any of the provided
        drawables.
    """
    # Create our initial maximum
    result = 0.0

    # Loop over histograms
    for drawable in drawables:
        # Unpack things if there is an error band
        if isinstance(drawable, tuple):
            drawable, error_band = drawable
        else:
            error_band = None

        # Compute the maximum for this drawable
        if is_histo(drawable) or is_stack(drawable) or is_scatter(drawable):
            maximum = drawable.GetMaximum()
        elif is_graph(drawable):
            # http://root.cern.ch/phpBB3/viewtopic.php?t=9070
            try:
                maximum = TMath.MaxElement(drawable.GetN(), drawable.GetY())
            except TypeError:
                # Could not convert argument 2, probably due to no points in
                # the graph. (GetN() == 0) Set a maximum of 1.0.
                maximum = 1.0
        elif is_function(drawable):
            maximum = drawable.GetMaximum()
        elif is_line(drawable):
            maximum = max(drawable.GetY1(), drawable.GetY2())
        elif is_function(drawable):
            maximum = 1.0
        else:
            raise ValueError('unsupported drawable type')

        # NOTE: Clever math hack.  Since drawable may be a THStack, we can't
        # (easily) do a bin-wise pairing and compute (value + error-high) for
        # each bin when looking for a maximum.  However, the bin which has the
        # maximum value will also have the maximum statistical and systematic
        # normalization uncertainty, so we can assume that the value returned
        # by GetMaximum() corresponds to the bin with the greatest error, and
        # thus we can just scan for the largest error and adding that to the
        # GetMaximum() result gives the answer we would get from bin-wise
        # pairing.  Of course, even if we didn't get the exact answer here,
        # we'd still be at-or-above the true maximum value, which is all we
        # really care about for plotting purposes.
        # If there is no error band, we just add enough room for statistical
        # error.
        if error_band is not None:
            maximum_error = 0.0
            for i in xrange(error_band.GetN()):
                maximum_error = max(maximum_error, error_band.GetErrorYhigh(i))
            maximum += maximum_error
        elif maximum < 5:
            maximum *= 1.2
        else:
            maximum += sqrt(maximum)

        # Update the result
        result = max(result, maximum)

    return result


def ratio_histogram(numerator, denominator, y_title = 'Data / Background'):
    """Creates a ratio histogram by dividing a numerator histogram by a
    denominator histogram.  Errors are calculated under the assumption of error
    on the numerator histogram only (the errors for the denominator histogram
    should be calculated by owls_hep.uncertainty.ratio_uncertainty_band).  This
    method also provides some basic styling of the ratio histogram, disabling
    statistics and title, and setting markers appropriately.

    Args:
        numerator: A single histogram, an iterable of histograms, or a THStack
            object which represents the data to use in the numerator of the
            ratio division
        denominator: A single histogram, an iterable of histograms, or a
            THStack object which represents the data to use in the numerator of
            the ratio division.  This must have the same binning as numerator.
        y_title: The title for the y-axis

    Returns:
        A ROOT histogram representing the ratio of numerator/denominator.
    """
    # Create our result based off of the numerator (it will have bin errors
    # enabled)
    result = combined_histogram(numerator)

    # Create the denominator
    combined_denominator = combined_histogram(denominator)

    # Disable errors on the denominator (they should be handled in an
    # uncertainty band around unity)
    for bin in xrange(0, combined_denominator.GetNbinsX() + 2):
        combined_denominator.SetBinError(bin, 0.0)

    # Divide by the denominator
    result.Divide(combined_denominator)

    # Do some styling on the result
    result.SetTitle('')
    result.SetStats(0)
    result.SetMarkerStyle(21)

    # Set title
    result.GetYaxis().SetTitle(y_title)

    return result


def histogram_stack(*histograms):
    """Creates a THStack object with a unique identifier from the specified
    histograms.

    This method is useful due to THStack freaking out if a new THStack is
    created with the same name.

    Args:
        histograms: Each argument of this function after plot may be a single
            histogram, an iterable of histograms (each of which should be
            plotted), or even an existing THStack object whose component
            histograms should be included in the new stack.  The histograms
            should be specified from top-to-bottom.

    Returns:
        An initialized THStack object containing the specified histograms.
    """
    # Generate an iterable of all histograms provided
    histograms = chain(*(drawable_iterable(h, unpack_stacks = True)
                         for h
                         in histograms))

    # Create a new THStack object with a unique identifier
    stack = THStack(_rand_uuid(), '')
    SetOwnership(stack, False)

    # Add histograms
    map(stack.Add, histograms)

    return stack


class Plot(object):
    """Structural class for representing, accessing, and maintaining references
    to ROOT graphical elements forming a plot, potentially with a ratio
    subplot.
    """

    # Plotting 'constants' for the plot class.  Ideally, one would allow these
    # to be flexible, but unfortunately ROOT's coordinate system is extremely
    # inconsistent and fragile, so it is best to fix these values here.  You
    # can change them dynamically with Plot.Whatever = value, but it is
    # probably best to leave them alone.
    PLOT_WIDTH = 1280 # px
    PLOT_HEIGHT = 1024 # px
    #PLOT_MARGINS = (0.125, 0.05, 0.1, 0.1) # Left, Right, Bottom, Top
    PLOT_MARGINS = (0.125, 0.05, 0.1, 0.07) # Left, Right, Bottom, Top
    PLOT_MARGINS_WITH_RATIO = (0.125, 0.05, 0.025, 0.1)
    PLOT_RATIO_MARGINS = (0.125, 0.05, 0.325, 0.05)
    PLOT_TITLE_X = 0.5
    PLOT_TITLE_Y = 0.95
    PLOT_TITLE_TEXT_SIZE = 0.04
    PLOT_TITLE_TEXT_COLOR = 1
    PLOT_TITLE_TEXT_FONT = 42
    PLOT_HEADER_HEIGHT = 400 # px
    PLOT_LEGEND_LEFT = 0.45
    PLOT_LEGEND_RIGHT = 0.95
    PLOT_LEGEND_BOTTOM = 0.7
    PLOT_LEGEND_BOTTOM_WITH_RATIO = 0.63
    PLOT_LEGEND_TOP = 0.90
    PLOT_LEGEND_TOP_WITH_RATIO = 0.86
    PLOT_LEGEND_TEXT_SIZE = 0.025
    PLOT_LEGEND_TEXT_SIZE_WITH_RATIO = 0.03
    PLOT_LEGEND_ROW_SIZE = 0.04
    PLOT_LEGEND_ROW_SIZE_WITH_RATIO = 0.045
    PLOT_LEGEND_N_COLUMNS = 1
    PLOT_STAT_LEFT = 0.55
    PLOT_STAT_LEFT_WITH_RATIO = 0.60
    PLOT_STAT_RIGHT = 0.85
    PLOT_STAT_RIGHT_WITH_RATIO = 0.93
    PLOT_STAT_BOTTOM = 0.15
    PLOT_STAT_BOTTOM_WITH_RATIO = 0.07
    PLOT_STAT_TOP = 0.4
    PLOT_STAT_TOP_WITH_RATIO = 0.45
    PLOT_STAT_TEXT_FONT = 42
    PLOT_STAT_TEXT_SIZE = 0.03
    PLOT_STAT_TEXT_SIZE_WITH_RATIO = 0.04
    PLOT_RATIO_FRACTION = 0.3 # fraction of canvas height
    PLOT_X_AXIS_TITLE_SIZE = 0.042
    PLOT_X_AXIS_TITLE_SIZE_WITH_RATIO = 0.14
    PLOT_X_AXIS_TITLE_OFFSET = 0.95
    PLOT_X_AXIS_TITLE_OFFSET_WITH_RATIO = 0.96
    PLOT_X_AXIS_LABEL_SIZE_WITH_RATIO = 0.12
    PLOT_Y_AXIS_LABEL_OFFSET = 0.01
    PLOT_Y_AXIS_TITLE_SIZE = 0.042
    PLOT_Y_AXIS_TITLE_SIZE_WITH_RATIO = 0.06
    PLOT_Y_AXIS_TITLE_OFFSET = 1.0
    PLOT_Y_AXIS_TITLE_OFFSET_WITH_RATIO = 0.95
    PLOT_Y_AXIS_LABEL_SIZE_WITH_RATIO = 0.05
    PLOT_RATIO_Y_AXIS_TITLE_SIZE = 0.12
    PLOT_RATIO_Y_AXIS_TITLE_OFFSET = 0.40
    PLOT_RATIO_Y_AXIS_LABEL_SIZE = 0.12
    PLOT_RATIO_Y_AXIS_LABEL_OFFSET = PLOT_Y_AXIS_LABEL_OFFSET
    PLOT_RATIO_Y_AXIS_NDIVISIONS = 504
    PLOT_RATIO_Y_AXIS_MINIMUM = 0.6
    PLOT_RATIO_Y_AXIS_MAXIMUM = 1.4
    PLOT_ERROR_BAND_FILL_STYLE = 3254 # Diagonal lines
    PLOT_ERROR_BAND_FILL_COLOR = 13 # Gray
    PLOT_ERROR_BAND_LINE_WIDTH = 0
    PLOT_ERROR_BAND_LINE_COLOR = 0
    PLOT_RATIO_ERROR_BAND_FILL_STYLE = 3254 # Diagonal lines
    PLOT_RATIO_ERROR_BAND_FILL_COLOR = 807 # Orange
    PLOT_RATIO_ERROR_BAND_LINE_WIDTH = 0
    PLOT_RATIO_ERROR_BAND_LINE_COLOR = 0
    # Stamp settings
    PLOT_ATLAS_STAMP_TEXT_SIZE = 0.035
    PLOT_ATLAS_STAMP_TEXT_SIZE_WITH_RATIO = 0.05
    PLOT_ATLAS_STAMP_TEXT_COLOR = 1
    PLOT_ATLAS_STAMP_TEXT_FONT = 42
    PLOT_ATLAS_STAMP_LEFT = 0.18
    PLOT_ATLAS_STAMP_TOP = 0.875
    PLOT_ATLAS_STAMP_TOP_WITH_RATIO = 0.82
    # Stamp specializations
    PLOT_ATLAS_STAMP_ATLAS_TEXT_FONT = 72
    PLOT_ATLAS_STAMP_ATLAS_LABEL_LEFT = 0.28
    PLOT_ATLAS_STAMP_LUMINOSITY_OFFSET = 0.036
    PLOT_ATLAS_STAMP_LUMINOSITY_OFFSET_WITH_RATIO = 0.05
    PLOT_ATLAS_STAMP_LUMINOSITY_SIZE = 0.062
    PLOT_ATLAS_STAMP_LUMINOSITY_SIZE_WITH_RATIO = 0.085

    def __init__(self,
                 title = '',
                 x_title = None,
                 y_title = None,
                 plot_header = True,
                 ratio = False,
                 x_range = None,
                 y_max = None):
        """Initializes a new instance of the Plot class.

        Args:
            title: The title to set for the histogram
            plot_header: Whether or not to include whitespace at the top of the
                plot for the ATLAS label and legend
            ratio: Whether or not to include a ratio plot
            x_range: A tuple of (x_min, x_max)
            y_max: The maximum Y axis value
        """
        # Store the title
        self._title = title
        self._x_title, self._y_title = x_title, y_title

        # Store whether or not the user wants to create a plot header
        self._plot_header = plot_header

        # Calculate a unique name for the plot components
        name = _rand_uuid()

        # Create a canvas
        self._canvas = TCanvas(name + '_canvas',
                               name,
                               int(self.PLOT_WIDTH),
                               int(self.PLOT_HEIGHT))
        SetOwnership(self._canvas, False)

        # Create the main plot and draw it
        self._plot = TPad(
            name + '_plot',
            name,
            0.0,
            (self.PLOT_RATIO_FRACTION
             if ratio
             else 0.0),
            1.0,
            1.0
        )
        SetOwnership(self._plot, False)
        self._plot.SetMargin(*(self.PLOT_MARGINS_WITH_RATIO
                               if ratio
                               else self.PLOT_MARGINS))
        self._plot.Draw()

        # HACK: Draw the plot title.
        # https://root.cern.ch/phpBB3/viewtopic.php?t=18282. Wonderful.
        self._draw_title()

        # Store ranges
        self._x_range = x_range
        if y_max is not None:
            self._set_maximum_value(y_max)

        # Switch back to the context of the canvas
        self._canvas.cd()

        # Create a ratio plot and draw it if requested
        if ratio:
            self._ratio_plot = TPad(
                name + '_ratio',
                name,
                0.0,
                0.0,
                1.0,
                self.PLOT_RATIO_FRACTION
            )
            SetOwnership(self._ratio_plot, False)
            self._ratio_plot.SetMargin(*self.PLOT_RATIO_MARGINS)
            self._ratio_plot.SetGridy(True)
            self._ratio_plot.Draw()
        else:
            self._ratio_plot = None

        # Track whether or not we've already drawn to the main pad
        self._drawn = False

        # Track whether or not we've already drawn to the ratio pad
        self._ratio_drawn = False

        # Track that object which sets up the axes in the main plot
        self._axes_object = None

        # Create a structure to track any histograms we generate internally
        # which need to be added to any legends created
        self._legend_extras = []

        # Create lists of the cloned drawables, just to be certain
        self._drawables = []
        self._ratio_drawables = []

    def save(self, path, extensions = ['pdf']):
        """Saves this plot to file.

        Args:
            path: The path where the plot should be saved.
        """
        # Force an update of the canvas
        self._canvas.Update()

        # Save to file
        for e in extensions:
            self._canvas.SaveAs(path + '.' + e)

    def _get_maximum_value(self):
        """Returns the currently set maximum value (possibly None).
        """
        if hasattr(self, '_maximum_value'):
            return self._maximum_value
        return None

    def _set_maximum_value(self, value):
        """Sets the current maximum value, possibly including room for a plot
        header.

        Args:
            value: The value to set
        """
        # Check if the current value is not None, and if so, throw an error
        # because this property should not be set twice
        if self._get_maximum_value() is not None:
            raise RuntimeError('maximum value should not be set twice')

        # If the value is None, ignore it
        if value is None:
            return

        # If the user wants a plot header, then add space for one
        if self._plot_header:
            # Grab the plot pad height (in pixels)
            plot_height = (
                self.PLOT_HEIGHT * (self._plot.GetY2() - self._plot.GetY1())
            )

            # Adjust the height
            value *= (plot_height + self.PLOT_HEADER_HEIGHT) / plot_height

        # Set the value
        self._maximum_value = value

    def set_log_scale(self, log_scale = True):
        """Set log scale on the Y axis for this plot."""
        self._plot.SetLogy(int(log_scale))

    def draw(self, *drawables_styles_options):
        """Plots a collection of plottables to the main plot pad.  All TH1
        objects are drawn with error bars.  THStack elements are only drawn
        with an error band if one is provided.

        This method may only be called once

        Args:
            drawables_styles_options: Each argument of this function must be
                of the form (object, style, options), where object is one of
                the following:

                - A TH1 object
                - A TH2 object
                - A THStack object
                - A tuple of the form (THStack, TGraph) where the latter
                  represents error bars
                - A TGraph object
                - A TLine object

                style is a tuple of the form (line_color, fill_color,
                marker_style), and options is a string which will be used for
                the options argument of the object's Draw method.  Plottables
                will be rendered in the order provided.  Axes drawing options
                (e.g.  'a' or 'same' should not be provided and will be set
                automatically).  A TLine may not be the first drawable
                element.
        """
        # Make sure there are drawables
        if len(drawables_styles_options) == 0:
            raise ValueError('must provide at least one plottable')

        # Check if we've already drawn
        if self._drawn:
            raise RuntimeError('cannot draw twice to a plot')
        self._drawn = True

        # Remove None-valued drawables
        drawables_styles_options = tuple(((d,s,o) for d,s,o \
                in drawables_styles_options if d is not None))

        # Extract drawables
        drawables, _, _ = zip(*drawables_styles_options)

        # Check if there is a maximum value set, and if not, set it
        if self._get_maximum_value() is None:
            self._set_maximum_value(maximum_value(drawables))

        # Move to the context of the plot pad
        self._plot.cd()

        # Iterate through and draw drawables based on type
        first = True
        for drawable, style, option in drawables_styles_options:
            # Check if this a tuple of histogram, error_band
            if isinstance(drawable, tuple):
                drawable, error_band = drawable
            else:
                error_band = None

            # Make a clone of the drawable so we don't modify it
            o = clone(drawable)
            SetOwnership(o, False)

            # Add it to the list of drawables
            self._drawables.append(o)

            # Set the title appropriately
            if not is_line(o):
                o.SetTitle(drawable.GetTitle())

            # Style the drawable before it is drawn
            if style is not None:
                if is_line(drawable) or is_function(drawable):
                    style_line(o, *style)
                else:
                    style_histogram(o, *style)

            # Set the maximum value of the drawable if supported
            # HACK: I wish this could go into _handle_axes, but apparently it
            # can't because ROOT sucks and this has to be set on EVERY
            # drawable, not just the one with the axes.
            if is_scatter(o):
                o.SetMinimum(0)
            if is_histo(o) or is_graph(o) or is_stack(o) or is_function(o):
                o.SetMaximum(self._get_maximum_value())
                # With TGraph, this is sometimes necessary. Perhaps with TH1
                # too. I'm not sure what happens if we set log scale, but
                # we'll cross that bridge then.
                o.SetMinimum(0)

            # Include axes if we need to. Store the x-axis range.
            if first:
                if is_line(o):
                    raise ValueError('TLine may not be first drawable')
                if is_graph(o):
                    option += 'a'
            else:
                option += 'same'
            first = False

            # Draw the drawable
            o.Draw(option)

            # TODO: This method of plotting the stats box is a huge hack. We
            # should plot fit functions separately, and move the stats box
            # plotting to its own function. Home grow everything, the only
            # way you can make ROOT work.
            if is_graph(o) or is_histo(o):
                if len(o.GetListOfFunctions()) > 0:
                    # HACK: Need to call Update() to paint the fit stats
                    self._plot.Update()
                    stats = o.FindObject("stats")
                    if stats:
                        stats.SetTextFont(Plot.PLOT_STAT_TEXT_FONT)
                        stats.SetTextSize((Plot.PLOT_STAT_TEXT_SIZE_WITH_RATIO
                                           if self._ratio_plot
                                           else Plot.PLOT_STAT_TEXT_SIZE))
                        stats.SetX1NDC((Plot.PLOT_STAT_LEFT_WITH_RATIO
                                        if self._ratio_plot
                                        else Plot.PLOT_STAT_LEFT))
                        stats.SetY1NDC((Plot.PLOT_STAT_BOTTOM_WITH_RATIO
                                        if self._ratio_plot
                                        else Plot.PLOT_STAT_BOTTOM))
                        stats.SetX2NDC((Plot.PLOT_STAT_RIGHT_WITH_RATIO
                                        if self._ratio_plot
                                        else Plot.PLOT_STAT_RIGHT))
                        stats.SetY2NDC((Plot.PLOT_STAT_TOP_WITH_RATIO
                                        if self._ratio_plot
                                        else Plot.PLOT_STAT_TOP))

            # Handle axes
            if not is_line(o):
                self._handle_axes(o, option)

            # If there is an error band, draw it
            if error_band is not None:
                self._draw_error_band(error_band)

        # TODO: Verify this. It breaks 2D plotting.
        # HACK: Need to force a redraw of plot axes due to issue with ROOT:
        # http://root.cern.ch/phpBB3/viewtopic.php?f=3&t=14034
        #self._plot.RedrawAxis()

    def _handle_axes(self, drawable, option):
        """If there is no object currently registered as the owner of the axes
        drawn on the main plot, then this will set it.

        Args:
            drawable: The graph, histogram or stack whose axes were ALREADY
                drawn
            option: The option with which to draw the axes
        """
        # If we already have an axes object, ignore this one
        if self._axes_object is not None:
            return

        # Grab the histogram used for axes style/range manipulation
        if is_stack(drawable) or is_graph(drawable):
            axes_histogram = drawable.GetHistogram()
        else:
            axes_histogram = drawable
        self._axes_object = axes_histogram

        # Grab the histogram used for title manipulation
        if is_stack(drawable):
            title_histogram = drawable.GetHists()[0]
        else:
            title_histogram = drawable

        # Grab axes
        x_axis, y_axis = axes_histogram.GetXaxis(), axes_histogram.GetYaxis()

        # Grab titles from first histogram if not set explicitly
        if self._x_title is None:
            self._x_title = title_histogram.GetXaxis().GetTitle()
        if self._y_title is None:
            self._y_title = title_histogram.GetYaxis().GetTitle()

        if self._x_range is not None:
            #x_axis.SetRangeUser(*self._x_range)
            x_axis.SetLimits(*self._x_range)

        # Style x-axis, or hide it if this plot has a ratio plot
        if self._ratio_plot:
            x_axis.SetLabelOffset(999)
            x_axis.SetTitleOffset(999)
        else:
            x_axis.SetTitle(self._x_title)
            x_axis.SetTitleSize(self.PLOT_X_AXIS_TITLE_SIZE)
            x_axis.SetTitleOffset(self.PLOT_X_AXIS_TITLE_OFFSET)

        # Style y-axis
        if self._ratio_plot:
            y_axis.SetLabelSize(self.PLOT_Y_AXIS_LABEL_SIZE_WITH_RATIO)
        y_axis.SetLabelOffset(self.PLOT_Y_AXIS_LABEL_OFFSET)
        y_axis.SetTitle(self._y_title)
        y_axis.SetTitleSize(
            (self.PLOT_Y_AXIS_TITLE_SIZE_WITH_RATIO
             if self._ratio_plot
             else self.PLOT_Y_AXIS_TITLE_SIZE)
        )
        y_axis.SetTitleOffset(
            (self.PLOT_Y_AXIS_TITLE_OFFSET_WITH_RATIO
             if self._ratio_plot
             else self.PLOT_Y_AXIS_TITLE_OFFSET)
        )

        # Redraw the drawable with the new style
        drawable.Draw(option)

    def _draw_error_band(self, error_band):
        """Draws an error band on top of histogram objects.

        Args:
            error_band: The error band to draw (a TGraphAsymmErrors)
        """
        # Style it
        # HACK: Setting the marker style to 0 specifies this should be filled
        # in the legend
        error_band.SetMarkerStyle(0)
        error_band.SetMarkerSize(0)
        error_band.SetFillStyle(self.PLOT_ERROR_BAND_FILL_STYLE)
        error_band.SetFillColor(self.PLOT_ERROR_BAND_FILL_COLOR)
        error_band.SetLineWidth(self.PLOT_ERROR_BAND_LINE_WIDTH)
        error_band.SetLineColor(self.PLOT_ERROR_BAND_LINE_COLOR)

        # Draw it
        error_band.Draw('e2same')

        # Add it to the list of things we need to add to the legend
        self._legend_extras.append(error_band)

    def draw_ratio_histogram(self,
                             histogram,
                             draw_unity = True,
                             error_band = None):
        """Draws a ratio histogram to the ratio pad.

        Args:
            histogram: The ratio histogram to draw (use ratio_histogram)
            draw_unity: Whether or not to draw a line at 1
            error_band: An error band to draw under the ratio histogram
                (see owls_hep.uncertainty.ratio_uncertainty_band)

        The histogram X axis title is set by draw_histogram if not set
        explicitly. draw_ratio_histogram should therefore be called after
        draw_histogram.
        """
        # Check if we've already drawn
        if self._ratio_drawn:
            raise RuntimeError('cannot draw twice to a plot')
        self._ratio_drawn = True

        # Switch to the context of the ratio pad
        self._ratio_plot.cd()

        # Clone the histogram
        histogram = histogram.Clone(_rand_uuid())
        SetOwnership(histogram, False)

        # Style it
        x_axis, y_axis = histogram.GetXaxis(), histogram.GetYaxis()
        x_axis.SetTitleSize(self.PLOT_X_AXIS_TITLE_SIZE_WITH_RATIO)
        x_axis.SetTitleOffset(self.PLOT_X_AXIS_TITLE_OFFSET_WITH_RATIO)
        x_axis.SetLabelSize(self.PLOT_X_AXIS_LABEL_SIZE_WITH_RATIO)
        x_axis.SetTitle(self._x_title)
        if self._x_range:
            x_axis.SetLimits(*self._x_range)
            #x_axis.SetRangeUser(*self._x_range)
        else:
            x_axis.SetLimits(self._axes_object.GetXaxis().GetXmin(),
                             self._axes_object.GetXaxis().GetXmax())
            #x_axis.SetRangeUser(self._axes_object.GetXaxis().GetXmin(),
                                #self._axes_object.GetXaxis().GetXmax())
        y_axis.SetTitleSize(self.PLOT_RATIO_Y_AXIS_TITLE_SIZE)
        y_axis.SetTitleOffset(self.PLOT_RATIO_Y_AXIS_TITLE_OFFSET)
        y_axis.SetLabelSize(self.PLOT_RATIO_Y_AXIS_LABEL_SIZE)
        y_axis.SetLabelOffset(self.PLOT_RATIO_Y_AXIS_LABEL_OFFSET)
        y_axis.SetRangeUser(self.PLOT_RATIO_Y_AXIS_MINIMUM,
                            self.PLOT_RATIO_Y_AXIS_MAXIMUM)
        y_axis.SetNdivisions(self.PLOT_RATIO_Y_AXIS_NDIVISIONS, False)

        # Draw it
        # NOTE: Have to specify E0 or points out of the vertical range won't
        # have their error bars drawn:
        #   https://root.cern.ch/phpBB3/viewtopic.php?f=3&t=13329
        histogram.Draw('e0p')

        # Draw a line at unity if requested
        if draw_unity:
            # Calculate the line coordinates
            line_min = histogram.GetBinLowEdge(1)
            max_bin = histogram.GetNbinsX()
            line_max = (histogram.GetBinLowEdge(max_bin) +
                        histogram.GetBinWidth(max_bin))

            # Create and draw the line
            unit_line = TLine(line_min,
                              1.0,
                              line_max,
                              1.0)
            SetOwnership(unit_line, False)
            unit_line.SetLineColor(2) # Red
            unit_line.SetLineWidth(2)
            unit_line.Draw('same')

        # If an error band was provided, draw it and add it to our legend
        # elements
        if error_band:
            # Keep ownership of the error band
            SetOwnership(error_band, False)

            # Style it
            error_band.SetMarkerSize(0)
            error_band.SetFillStyle(self.PLOT_RATIO_ERROR_BAND_FILL_STYLE)
            error_band.SetFillColor(self.PLOT_RATIO_ERROR_BAND_FILL_COLOR)
            error_band.SetLineWidth(self.PLOT_RATIO_ERROR_BAND_LINE_WIDTH)
            error_band.SetLineColor(self.PLOT_RATIO_ERROR_BAND_LINE_COLOR)

            # Draw it
            error_band.Draw('e2same')

        # Now, if we've drawn unity or an error band, redraw our ratio
        # histogram so that its point lie on top of the unity line or error
        # band, but use 'same' so that the axes/ticks don't cover the red line
        if draw_unity or error_band:
            histogram.Draw('e0psame')

    def draw_ratios(self,
                    drawables_styles_options,
                    draw_unity = True,
                    y_range = None,
                    y_title = None):
        """Draws a drawable to the ratio pad.

        Args:
            drawable: The drawable to draw
            draw_unity: Whether or not to draw a line at 1
        """
        # Check if we've already drawn
        if self._ratio_drawn:
            raise RuntimeError('cannot draw twice to a plot')
        self._ratio_drawn = True

        # Switch to the context of the ratio pad
        self._ratio_plot.cd()

        # Iterate through and draw drawables based on type
        first = True
        for drawable, style, option in drawables_styles_options:
            # Make a clone of the drawable so we don't modify it
            o = clone(drawable)
            SetOwnership(o, False)

            # Add it to the list of drawables
            self._ratio_drawables.append(o)

            # Set the title appropriately
            if not is_line(o):
                o.SetTitle(drawable.GetTitle())

            # Style the drawable before it is drawn
            if style is not None:
                if is_line(drawable) or is_function(drawable):
                    style_line(o, *style)
                else:
                    style_histogram(o, *style)

            if not is_line(o):
                if y_range is not None:
                    o.SetMinimum(y_range[0])
                    o.SetMaximum(y_range[1])

            # Include axes if we need
            if first:
                if is_line(o):
                    raise ValueError('TLine may not be first drawable')
                x_axis, y_axis = o.GetXaxis(), o.GetYaxis()
                if is_graph(o):
                    option += 'a'
            else:
                option += 'same'
            first = False

            # Draw the drawable
            o.Draw(option)

        x_axis.SetTitleSize(self.PLOT_X_AXIS_TITLE_SIZE_WITH_RATIO)
        x_axis.SetTitleOffset(self.PLOT_X_AXIS_TITLE_OFFSET_WITH_RATIO)
        x_axis.SetLabelSize(self.PLOT_X_AXIS_LABEL_SIZE_WITH_RATIO)
        x_axis.SetTitle(self._x_title)
        if self._x_range:
            x_axis.SetLimits(*self._x_range)
            #x_axis.SetRangeUser(*self._x_range)
        else:
            x_axis.SetLimits(self._axes_object.GetXaxis().GetXmin(),
                             self._axes_object.GetXaxis().GetXmax())
            #x_axis.SetRangeUser(self._axes_object.GetXaxis().GetXmin(),
                                #self._axes_object.GetXaxis().GetXmax())
        y_axis.SetTitleSize(self.PLOT_RATIO_Y_AXIS_TITLE_SIZE)
        y_axis.SetTitleOffset(self.PLOT_RATIO_Y_AXIS_TITLE_OFFSET)
        y_axis.SetLabelSize(self.PLOT_RATIO_Y_AXIS_LABEL_SIZE)
        y_axis.SetLabelOffset(self.PLOT_RATIO_Y_AXIS_LABEL_OFFSET)
        y_axis.SetNdivisions(self.PLOT_RATIO_Y_AXIS_NDIVISIONS, False)
        if y_title is not None:
            y_axis.SetTitle(y_title)

        self._ratio_plot.Update()


    def _draw_title(self):
        """Draws a title on the plot.
        """
        title = TLatex()
        title.SetTextColor(self.PLOT_TITLE_TEXT_COLOR)
        title.SetTextFont(self.PLOT_TITLE_TEXT_FONT)
        title.SetNDC()
        title.SetTextSize(self.PLOT_TITLE_TEXT_SIZE)
        title.SetTextAlign(22)
        title.DrawLatex(
            self.PLOT_TITLE_X,
            self.PLOT_TITLE_Y,
            self._title
        )


    def draw_atlas_label(self,
                         luminosity = None,
                         sqrt_s = None,
                         custom_label = None,
                         atlas_label = None):
        """Draws an ATLAS stamp on the plot, with an optional categorization
        label.

        It is recommended that you construct the Plot with plot_header = True
        in order to make space for the label.

        Args:
            luminosity: The integrated luminosity, in pb^-1
            sqrt_s: The center of mass energy, in MeV
            label: The label to put after 'ATLAS', None to exclude the 'ATLAS'
                categorization entirely
        """
        # Change context to the plot pad
        self._plot.cd()

        # Create the latex object
        # TODO: Consider using TPaveText to overwrite drawn graphs and
        # histograms. At least for scatter plots.
        # TODO: Increase readability: Create two sets of constants -
        # one for plots with ratio and one for plots without. Select the
        # correct one in draw_ratio_histogram.
        stamp = TLatex()

        # Style it
        stamp.SetTextColor(self.PLOT_ATLAS_STAMP_TEXT_COLOR)
        stamp.SetTextSize((self.PLOT_ATLAS_STAMP_TEXT_SIZE_WITH_RATIO
                           if self._ratio_plot
                           else self.PLOT_ATLAS_STAMP_TEXT_SIZE))
        stamp.SetTextFont(self.PLOT_ATLAS_STAMP_TEXT_FONT)
        stamp.SetNDC()

        top = (self.PLOT_ATLAS_STAMP_TOP_WITH_RATIO
               if self._ratio_plot
               else self.PLOT_ATLAS_STAMP_TOP)

        # Print an ATLAS label on top
        if atlas_label is not None:
            # Draw the label
            stamp.SetTextFont(self.PLOT_ATLAS_STAMP_ATLAS_TEXT_FONT)
            stamp.DrawLatex(self.PLOT_ATLAS_STAMP_LEFT, top, 'ATLAS')
            stamp.SetTextFont(self.PLOT_ATLAS_STAMP_TEXT_FONT)
            stamp.DrawLatex(self.PLOT_ATLAS_STAMP_ATLAS_LABEL_LEFT,
                            top,
                            atlas_label)
            top -= (self.PLOT_ATLAS_STAMP_TEXT_SIZE_WITH_RATIO
                    if self._ratio_plot
                    else self.PLOT_ATLAS_STAMP_TEXT_SIZE) * 1.2


        # Draw the luminosity and sqrt(s)
        if luminosity is not None or sqrt_s is not None:
            text = ''
            if sqrt_s is not None:
                text += '#sqrt{{s}} = {0:.0f} TeV'.format(sqrt_s / 1.0e6)
                if luminosity is not None:
                    text += ', '
            if luminosity >= 1000.0:
                text += '{0:.1f} fb^{{-1}}'.format(luminosity / 1000.0)
            elif luminosity > 100.0:
                text += '{0:.2f} fb^{{-1}}'.format(luminosity / 1000.0)
            else:
                text += '{0:.1f} pb^{{-1}}'.format(luminosity)


            stamp.DrawLatex(self.PLOT_ATLAS_STAMP_LEFT, top, text)
            top -= (self.PLOT_ATLAS_STAMP_TEXT_SIZE_WITH_RATIO
                    if self._ratio_plot
                    else self.PLOT_ATLAS_STAMP_TEXT_SIZE) * 1.2

        # If requested, draw the custom label or the 'ATLAS' label,
        # preferring the former
        if custom_label is not None:
            # Draw each line of text, decreasing top for each step
            for text in custom_label:
                stamp.DrawLatex(self.PLOT_ATLAS_STAMP_LEFT, top, text)
                top -= (self.PLOT_ATLAS_STAMP_TEXT_SIZE_WITH_RATIO
                        if self._ratio_plot
                        else self.PLOT_ATLAS_STAMP_TEXT_SIZE) * 1.2

    def draw_pave(self, texts, position):
        """Draw a text box at the position and fill it with text.

        Args:
            texts: String or N-tuple of strings.
            positon: Absolute position of the form (x1, x2, y1, y2) as an
                     N-tuple of floats, or a string with one of the values
                     "{top,bottom}{left,right}"
        """
        if isinstance(position, basestring):
            if position == 'topleft':
                position = (0.15, 0.35, 0.85, 0.75)
            elif position == 'topright':
                position = (0.95, 0.75, 0.95, 0.85)
            elif position == 'bottomleft':
                position = (0.05, 0.25, 0.05, 0.15)
            elif position == 'topright':
                position = (0.95, 0.75, 0.05, 0.15)

        # Switch to the context of the main plot
        self._plot.cd()

        # Create the pave
        self._pave = TPaveText(position[0], position[2],
                               position[1], position[3], 'NDC')
        SetOwnership(self._pave, False)

        # Add the text
        if isinstance(texts, basestring):
            self._pave.AddText(texts)
        else:
            for t in texts:
                self._pave.AddText(t)

        # Draw the pave
        self._pave.Draw()

    def draw_legend(self, use_functions = False):
        """Draws a legend onto the plot with the specified histograms.

        It is recommended that you construct the Plot with plot_header = True
        in order to make space for the legend.

        Args:
            drawables: The elements to include in the legend (via AddEntry)
            use_functions: Add associated functions to the legend
        """
        # Check if we already have a legend
        if hasattr(self, '_legend'):
            raise RuntimeError('legend already exists on this plot')

        # Check if the plot has been drawn
        if not self._drawn:
            raise RuntimeError('plot must be drawn before the legend')

        # Remove None-valued drawables
        drawables = tuple((drawable for drawable
                           in self._drawables
                           if drawable is not None))

        # Remove TLine objects
        drawables = tuple((drawable for drawable
                           in drawables
                           if not is_line(drawable)))

        # If we shouldn't add functions to the legend, remove them
        if not use_functions:
            drawables = tuple((drawable for drawable
                               in drawables if not isinstance(drawable, TF1)))

        # Switch to the context of the main plot
        self._plot.cd()

        # Create the legend
        self._legend = TLegend(self.PLOT_LEGEND_LEFT,
                               (self.PLOT_LEGEND_BOTTOM_WITH_RATIO
                                if self._ratio_plot
                                else self.PLOT_LEGEND_BOTTOM),
                               self.PLOT_LEGEND_RIGHT,
                               (self.PLOT_LEGEND_TOP_WITH_RATIO
                                if self._ratio_plot
                                else self.PLOT_LEGEND_TOP))
        SetOwnership(self._legend, False)

        # Style it
        self._legend.SetTextSize((
            self.PLOT_LEGEND_TEXT_SIZE_WITH_RATIO
            if self._ratio_plot
            else self.PLOT_LEGEND_TEXT_SIZE
        ))
        self._legend.SetBorderSize(0)
        self._legend.SetFillStyle(0) # transparent
        self._legend.SetNColumns(self.PLOT_LEGEND_N_COLUMNS)

        # Create a chained list of all drawables.  We decompose THStack
        # objects in reverse order, i.e. top-to-bottom.
        drawables = \
            list(chain(*(drawable_iterable(h, True, True)
                         for h
                         in drawables)))

        # Add anything to this list that we created internally
        drawables.extend(self._legend_extras)

        # Because ROOT draws legend entries from left-to-right across rows and
        # not top-to-bottom along columns, we need to do a bit of a pivot on
        # the list so that the histograms appear in the vertical order of the
        # stack
        n_entries = len(drawables)
        n_col = self.PLOT_LEGEND_N_COLUMNS
        n_row = int(ceil(float(n_entries) / n_col))
        self._legend.SetY1(self._legend.GetY2() -
                n_row * (self.PLOT_LEGEND_ROW_SIZE_WITH_RATIO
                         if self._ratio_plot
                         else self.PLOT_LEGEND_ROW_SIZE))
        legend_order = []
        for r in xrange(0, n_row):
            for c in xrange(0, n_col):
                if (r * n_col + c) == n_entries:
                    # Don't need an outer break, this would only happen on the
                    # last row if n_row * n_col != n_entries
                    break
                legend_order.append(drawables[r + c * n_row])

        # Add the drawables
        for drawable in legend_order:
            SetOwnership(drawable, False)
            title = drawable.GetTitle()
            # HACK: Convention: legend for drawables with a non-default
            # marker style (data) to be drawn as line with point, and with
            # empty fill (signal) to be drawn as line
            if drawable.GetMarkerStyle() != 0:
                self._legend.AddEntry(drawable, title, 'ep')
            elif drawable.GetFillColor() == 0:
                self._legend.AddEntry(drawable, title, 'l')
            else:
                self._legend.AddEntry(drawable, title, 'f')

        # Draw the legend
        self._legend.Draw()
