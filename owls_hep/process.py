"""Provides models for processes and process patches.
"""


# System imports
from copy import deepcopy

# Six imports
from six import string_types

# owls-data imports
from owls_data.loading import load as load_data


# Set up default exports
__all__ = [
    'Patch',
    'Process',
]


class Patch(object):
    """Represents a patch to apply to a process' data.
    """

    def __hash__(self):
        """Returns a unique hash for the patch.

        This method should not be overridden.
        """
        # Grab the patch type
        patch_type = type(self)

        # Extract hashable components
        module = patch_type.__module__
        name = patch_type.__name__
        state = self.state()

        # Create a unique hash
        return hash((module, name, state))

    def state(self):
        """Returns a representation of the patch's internal state, if any.

        This method is used to generate a unique hash for the patch for the
        purposes of caching.  If a patch has no internal state, and it's
        behavior is determined entirely by its type, then the implementer need
        not override this method.  However, if a patch contains state which
        affects its patching behavior, this method needs to be overridden.  A
        simple tuple may be returned containing the state of the patch.

        Returns:
            A hashable object representing the internal state of the patch.
        """
        return ()

    def properties(self):
        """Returns a Python set of properties of the data required to evaluate
        the patch.

        Implementers must override this method.
        """
        raise NotImplementedError('abstract method')

    def __call__(self, data):
        """Applies the patch to a DataFrame.

        The provided DataFrame will be a copy which can be freely mutated.
        This method should return its input.

        Implementers must override this method.

        Args:
            data: The DataFrame to patch

        Returns:
            The modified DataFrame.
        """
        raise NotImplementedError('abstract method')


class Process(object):
    """Represents a physical process whose events may be encoded in one or more
    data files and which should be rendered according to a certain style.
    """

    def __init__(self,
                 name,
                 files,
                 tree,
                 label,
                 line_color = 1,
                 fill_color = 0,
                 marker_style = None):
        """Initializes a new instance of the Process class.

        Args:
            name: A name by which to refer to the process
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
        """
        # Store parameters
        self._name = name
        self._files = tuple(files)
        self._tree = tree
        self._label = label
        self._line_color = line_color
        self._fill_color = fill_color
        self._marker_style = marker_style

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
        # Hash only files, tree, and patches since those are all that really
        # matter for data loading
        return hash((self._files, self._tree, self._patches))

    @property
    def name(self):
        return self._name

    def load(self, properties):
        """Loads the given properties of the process data.

        The tree weights of the TTrees are included in the resultant DataFrame
        as the 'tree_weight' property.

        Args:
            properties: A Python set of property names (TTree branch names) to
                load

        Returns:
            A Pandas DataFrame containing the specified properties for the
            process.
        """
        # Compute the properties we need to load
        all_properties = set.union(properties,
                                   *(p.properties() for p in self._patches))

        # Load data, specifying ourselves as the cache name, because if we
        # apply patches, the resultant DataFrame will be mutated but still
        # transiently cached, and the load method won't know anything about it
        result = load_data(self._files, all_properties, {
            'tree': self._tree,
            'tree_weight_property': 'tree_weight'
        }, cache = self)

        # Apply patches
        for p in self._patches:
            result = p(result)

        # All done
        return result

    def retreed(self, tree):
        """Creates a new copy of the process with a different tree.

        Args:
            tree: The tree to set for the new process

        Returns:
            A copy of the process with the tree modified.
        """
        # Create the copy
        result = deepcopy(self)

        # Retree
        result._tree = tree

        # All done
        return result

    def patched(self, patch):
        """Creates a new copy of the process with a patch applied.

        Args:
            patch: The patch to apply in the new process

        Returns:
            A copy of the process with the additional patch applied.
        """
        # Create the copy
        result = deepcopy(self)

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
            histogram.SetMarkerSize(1)
            histogram.SetMarkerColor(histogram.GetLineColor())
        else:
            # HACK: Set marker style to an invalid value if not specified,
            # because we need some way to differentiate rendering in the legend
            histogram.SetMarkerStyle(0)

        # Make lines visible
        histogram.SetLineWidth(2)
