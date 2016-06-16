"""Provides models for processes and process patches.
"""


# System imports
import warnings
from inspect import getsource
from copy import copy
from os.path import isfile
from os import stat

# Six imports
from six import string_types

# ROOT imports
from ROOT import TChain, TColor, SetOwnership

# owls-hep imports
from owls_hep.expression import multiplied
from owls_hep.output import print_warning


# Set up default exports
__all__ = [
    'Patch',
    'Process',
]

class Patch(object):
    """A reusable process patch weighs/filters events according to an
    expression.
    """

    def __init__(self, selection):
        """Initializes a new instance of the Patch class.

        Args:
            selection: The selection expression to apply to the process data
        """
        self._selection = selection

    def state(self):
        """Returns a representation of the patch's internal state, if any.
        """
        return (self._selection,)

    def selection(self):
        """Returns the selection string for the patch.

        Returns:
            The selection string.
        """
        return self._selection


class Process(object):
    """Represents a physical process whose events may be encoded in one or more
    data files and which should be rendered according to a certain style.
    """

    def __init__(self,
                 files,
                 tree,
                 label,
                 sample_type = 'undef',
                 friends = (),
                 line_color = 1,
                 fill_color = 0,
                 marker_style = None,
                 metadata = {}):
        """Initializes a new instance of the Process class.

        Args:
            files: An iterable of ROOT file paths for files representing the
                process
            tree: The ROOT TTree path within the files to use
            label: The ROOT TLatex label string to use when rendering the
                process
            line_color: The ROOT TColor number or hex string (#rrggbb) to use
                as the line color when rendering the process
            fill_color: The ROOT TColor number or hex string (#rrggbb) to use
                as the fill color when rendering the process
            marker_style: The ROOT TMarker number to use as the marker style
                when rendering the process
            metadata: A (pickleable) object containing optional metadata
        """
        # Store parameters
        self._files = tuple(files)
        self._files_size_time = None
        self._tree = tree
        self._label = label
        self._sample_type = sample_type
        self._friends = friends
        self._line_color = line_color
        self._fill_color = fill_color
        self._marker_style = marker_style
        self._metadata = metadata

        # Translate hex colors if necessary
        if isinstance(self._line_color, string_types):
            self._line_color = TColor.GetColor(self._line_color)
        if isinstance(self._fill_color, string_types):
            self._fill_color = TColor.GetColor(self._fill_color)

        # Create initial patches container
        self._patches = ()

    def __hash__(self):
        """Returns a hash for the process.
        """
        # Hash the state
        return hash(self.state())

    def _get_files_size_time(self):
        """Populate the file sizes and modification times tuple.
        """
        if self._files_size_time is None:
            self._files_size_time = tuple([(stat(f).st_size, stat(f).st_mtime)
                                           for f in self._files])

    def state(self):
        """Returns a the state for the process.
        """
        # Use only files, tree, patches, friends, and sample_type in the
        # state since those are all that really matter for data processing
        self._get_files_size_time()
        return (self._files,
                self._files_size_time,
                self._tree,
                self._sample_type,
                self._friends,
                self.patches())

    def label(self):
        """Returns the label of the process.
        """
        return self._label

    def files(self):
        """Returns the files for the process.
        """
        return self._files

    def sample_type(self):
        """Returns the sample type for the process.
        """
        return self._sample_type

    def metadata(self):
        """Returns the metadata for the process, if any.
        """
        return self._metadata

    def patches(self):
        """Returns an expression of patches for the process, if any.
        """
        return multiplied(*[p.selection() for p in self._patches])

    # NOTE: We could instead return a list of TTrees/TFiles, because using
    # individual TFile/TTree objects might be slightly faster than creating
    # one huge TChain.
    def load(self):
        """Loads the process data.

        Returns:
            A TChain for the process.
        """

        chain = TChain(self._tree)
        for f in self._files:
            if not isfile(f):
                raise RuntimeError('file does not exist {0}'.format(f))
            chain.Add(f)

        for friend in self._friends:
            chain.AddFriend(self._load_friend(*friend))

        return chain

    def _load_friend(self, file, tree, index):
        if not isfile(file):
            raise RuntimeError('file does not exist {0}'.format(file))

        chain = TChain(tree)
        chain.Add(file)
        if index is not None:
            chain.BuildIndex(index)

        return chain

    def retreed(self, tree):
        """Creates a new copy of the process with a different tree.

        Args:
            tree: The tree to set for the new process

        Returns:
            A copy of the process with the tree modified.
        """
        # Create the copy
        result = copy(self)

        # Retree
        result._tree = tree

        # All done
        return result

    def patched(self,
                patch,
                label = None,
                line_color =  None,
                fill_color = None,
                marker_style = None,
                metadata = None):
        """Creates a new copy of the process with a patch applied.

        Args:
            patch: The patch to apply in the new process

        Returns:
            A copy of the process with the additional patch applied.
        """
        # Create the copy
        result = copy(self)
        if label is not None: result._label = label
        if line_color is not None: result._line_color = line_color
        if fill_color is not None: result._fill_color = fill_color
        if marker_style is not None: result._marker_style = marker_style
        if metadata is not None: result._metadata = metadata

        # Add the patch
        result._patches += (patch,)

        # All done
        return result

    def style(self, histogram):
        """Applies the process' style to a histogram.

        Args:
            histogram: The histogram to style
        """
        # Set title
        histogram.SetTitle(self._label)

        # Set line color
        histogram.SetLineColor(self._line_color)

        # Set fill style and color
        histogram.SetFillStyle(1001)
        histogram.SetFillColor(self._fill_color)

        # Set marker style
        if self._marker_style is not None:
            histogram.SetMarkerStyle(self._marker_style)
            # TODO: This should be configurable
            histogram.SetMarkerSize(2)
            histogram.SetMarkerColor(histogram.GetLineColor())
        else:
            # HACK: Set marker style to an invalid value if not specified,
            # because we need some way to differentiate rendering in the legend
            histogram.SetMarkerStyle(0)

        # Make lines visible
        histogram.SetLineWidth(2)

class MultiProcess(object):
    """Represents a combined process whose events may be encoded in one or
    more data processes and which should be rendered according to a certain
    style.
    """

    def __init__(self,
                 subprocesses,
                 tree,
                 label,
                 line_color = 1,
                 fill_color = 0,
                 marker_style = None,
                 metadata = None):
        """Initializes a new instance of the Process class.

        Args:
            subporocesses: An iterable of processes
            label: The ROOT TLatex label string to use when rendering the
                process
            line_color: The ROOT TColor number or hex string (#rrggbb) to use
                as the line color when rendering the process
            fill_color: The ROOT TColor number or hex string (#rrggbb) to use
                as the fill color when rendering the process
            marker_style: The ROOT TMarker number to use as the marker style
                when rendering the process
            metadata: A (pickleable) object containing optional metadata
        """
        # Store parameters
        self._subprocesses = subprocesses
        self._label = label
        self._line_color = line_color
        self._fill_color = fill_color
        self._marker_style = marker_style
        self._metadata = metadata

        # Translate hex colors if necessary
        if isinstance(self._line_color, string_types):
            self._line_color = TColor.GetColor(self._line_color)
        if isinstance(self._fill_color, string_types):
            self._fill_color = TColor.GetColor(self._fill_color)

    def __hash__(self):
        raise NotImplementedError('method not supported')

    def load(self, properties):
        raise NotImplementedError('method not supported')

    def retreed(self, tree):
        raise NotImplementedError('method not supported')

    def patched(self, patch):
        raise NotImplementedError('method not supported')
