"""Provides models for regions and region variations.
"""

# Future imports
from __future__ import print_function

# System imports
from inspect import getsource
import re
from copy import copy

# owls-data imports
from owls_hep.expression import multiplied


# Set up default exports
__all__ = [
    'Variation',
    'Reweighted',
    'Region'
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


class Region(object):
    """Represents a region (a selection and weight) in which processes can be
    evaluated.
    """

    def __init__(self,
                 selection,
                 weight,
                 label,
                 sample_weights = {},
                 metadata = {}):
        """Initialized a new instance of the Region class.

        Args:
            selection: A string representing selection for the region, or an
                empty string for no selection
            weight: A string representing the weight for the region, or an
                empty string for no weighting
            label: The ROOT TLatex label string to use when rendering the
                region
            sample_weights: Weights to apply to the selection based on sample
                type. Should match the sample types of the processes, for
                example 'mc' and 'data'.
            metadata: A (pickleable) object containing optional metadata
        """
        # Store parameters
        self._selection = selection
        self._weight = weight
        self._label = label
        self._sample_weights = sample_weights
        self._metadata = metadata
        self._weighted = True

        # Create initial variations container
        self._variations = ()

    def __hash__(self):
        """Returns a hash for state of the region.
        """
        # Only hash those parameters which affect evaluation
        return hash(self.state())

    def state(self):
        """Returns the state of the region.
        """
        # Only hash those parameters which affect evaluation
        return (
            self._selection,
            self._weight,
            self._weighted,
            self._variations,
            tuple(sorted(self._sample_weights.iteritems())),
        )

    def __str__(self):
        """Returns the string representation of the region.
        """
        return 'Region({0}, {1})'.format(self._label, self.state())

    def label(self):
        """Returns the label for the region, if any.
        """
        return self._label

    def metadata(self):
        """Returns metadata for this region, if any.
        """
        return self._metadata

    def varied(self, variations):
        """Creates a copy of the region with the specified variation applied.

        Args:
            variations: The variation(s) to apply

        Returns:
            A duplicate region, but with the specified variation applied.
        """
        # Create the copy
        result = copy(self)

        # Add the variation
        if isinstance(variations, tuple):
            result._variations += variations
        else:
            result._variations += (variations,)

        return result

    # NOTE: This function is obsolete. I don't know when it would never be
    # useful, since weights are such an integral part of the simulation.
    #def weighted(self, weighting_enabled):
        #"""Creates a copy of the region with weighting turned on or off.

        #If there is no change to the weighting, self will be returned.

        #Args:
            #weighting_enabled: Whether or not to enable weighting

        #Returns:
            #A duplicate region, but with weighting set to weighting_enabled.
        #"""
        ## If there's no change, return self
        #if weighting_enabled == self._weighted:
            #return self

        ## Create a copy
        #result = copy(self)

        ## Change weighting status
        #result._weighted = weighting_enabled

        ## All done
        #return result

    def selection_weight(self, sample_type):
        """Returns a string of "selection * weight" with all variations
        applied.
        """
        # Grab resultant weight/selection
        selection = self._selection
        try:
            weight = multiplied(self._weight,
                                self._sample_weights[sample_type])
        except:
            weight = self._weight

        # Apply any variations
        for v in self._variations:
            selection, weight = v(selection, weight)

        # Return the product of the selection and weight expressions
        return multiplied(selection, weight)
