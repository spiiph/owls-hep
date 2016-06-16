"""Provides models for region variations
"""

# System imports
from inspect import getsource

# owls-hep imports
from owls_hep.expression import multiplied, anded, variable_substituted

# Set up default exports
__all__ = [
    'Variation',
    'Reweighted',
    'Filtered',
    'ReplaceWeight'
]

class Variation(object):
    """Represents a variation which can be applied to a region.
    """

    def __hash__(self):
        """Returns a unique hash for the patch.

        This method should not be overridden.
        """
        # HACK: Use the implementation of the variation in the hash, because
        # the behavior of the variation is what should determine hash equality,
        # and it's impossible to determine solely on type if the implementation
        # changes.
        if not isinstance(self.state(), tuple):
            raise TypeError('Variation state is not a tuple ({0})'. \
                    format(self.__class__))

        if None in self.state():
            print('Warning: Variation {0} has \'None\' in state!'.\
                    format(self, self.state()))

        return hash((self.state(), getsource(self.__call__)))

    def state(self):
        """Returns a representation of the variation's internal state, if any.

        This method is used to generate a unique hash for the variation for the
        purposes of caching.  If a variation has no internal state, and it's
        behavior is determined entirely by its type, then the implementer need
        not override this method.  However, if a variation contains state which
        affects its patching behavior, this method needs to be overridden.  A
        simple tuple may be returned containing the state of the variation.

        Returns:
            A hashable object representing the internal state of the variation.
        """
        return ()

    def __call__(self, selection, weight):
        """Applies a variation to a region's weight and selection.

        Implementers must override this method.

        Args:
            selection: The existing selection expression
            weight: The existing weight expression

        Returns:
            A tuple of the form (varied_selection, varied_weight).
        """
        raise NotImplementedError('abstract method')


class Reweighted(Variation):
    """A reusable region variation that multiplies an expression into the
    region weight.
    """

    def __init__(self, weight):
        """Initializes a new instance of the Reweighted class.

        Args:
            weight: The weight expression to incorporate into the region
        """
        # Store the weight
        self._weight = weight

    def state(self):
        """Returns a representation of the variation's internal state.
        """
        return (self._weight,)

    def __call__(self, selection, weight):
        """Add's an expression to a region's weight.

        Args:
            selection: The existing selection expression
            weight: The existing weight expression

        Returns:
            A tuple of the form (varied_selection, varied_weight).
        """
        return (selection, multiplied(weight, self._weight))

class Filtered(Variation):
    """A region variation that ANDs a selection and optionally a weight
    variable into the selection.
    """

    def __init__(self, selection, weight = None):
        """Initializes a new instance of the Filtered class.

        Args:
                selection:      The expression to incorporate into the region
                                to filter out events
                weight:         An optional weight to apply to the event
        """
        # Store the trigger_name
        self._selection = selection
        self._weight = weight

    def state(self):
        """Returns a representation of the variation's internal state.
        """
        if self._weight is None:
            return (self._selection,)
        else:
            return (self._selection, self._weight)

    def __call__(self, selection, weight):
        """Add's an expression to a region's weight.

        Args:
            selection: The existing selection expression
            weight: The existing weight expression

        Returns:
            A tuple of the form (varied_selection, varied_weight).
        """
        if self._weight is not None:
            return (anded(selection, self._selection),
                    multiplied(weight, self._weight))
        else:
            return (anded(selection, self._selection), weight)

    def __str__(self):
        """Return a string representation of the variation.
        """
        if self._weight is not None:
            return 'Filtered({0}, {1})'.format(self._selection, self._weight)
        else:
            return 'Filtered({0})'.format(self._selection)

class ReplaceWeight(Variation):
    """A region variation that replaces a weight (single event weight or
    combination thereof) with a new weight (e.g. a systematic variation).
    """

    def __init__(self, weight, variation):
        """Initializes a new instance of the ReplaceWeight class

        Args:
                weight:         Weight in the form of a regular expression
                variation:      Variation to replace weight
        """
        # Store the trigger_name
        self._weight = weight
        self._variation = variation

    def state(self):
        """Returns a representation of the variation's internal state.
        """
        return (self._weight, self._variation)

    def __call__(self, selection, weight):
        """Add's an expression to a region's weight.

        Args:
            selection: The existing selection expression
            weight: The existing weight expression

        Returns:
            A tuple of the form (varied_selection, varied_weight).
        """
        return (selection,
                variable_substituted(weight, self._weight, self._variation))

    def __str__(self):
        """Return a string representation of the variation.
        """
        return 'ReplaceWeight({0})'.format(self._variation)
