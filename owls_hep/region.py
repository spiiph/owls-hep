"""Provides models for regions
"""

# Future imports
from __future__ import print_function

# System imports
from copy import deepcopy

# owls-hep imports
from owls_hep.expression import multiplied
from owls_hep.variations import Variation


# Set up default exports
__all__ = [
    'Region'
]

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
        if isinstance(self._label, list) or isinstance(self._label, tuple):
            return self._label
        else:
            return [self._label]

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
        result = deepcopy(self)

        # Add the variation
        # NOTE: It's useful to check if the variation actually is a subclass
        # of Variation. Mistakes here are particularly hard to decode.
        if isinstance(variations, tuple):
            for v in variations:
                if not isinstance(variations, Variation):
                    raise TypeError('{} is not a subclass of Variation'. \
                            format(v))
            result._variations += variations
        else:
            if not isinstance(variations, Variation):
                raise TypeError('{} is not a subclass of Variation'. \
                        format(variations))
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

    def selection(self):
        """Returns a string of "selection * weight" with all variations
        applied.
        """
        # Grab resultant weight/selection
        selection = self._selection

        # Apply any variations
        for v in self._variations:
            selection, _ = v(selection, '')
        return selection

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
