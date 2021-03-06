"""Provides inspection, manipulation, and composition methods for string-based
expressions.
"""


# System imports
import re
from functools import partial

# Create a utility to substitute definitions enclosed in [] within a
# selection string. This functionality is used mostly in regions.py and
# models.py files to increase level of abstraction.
_finder = re.compile('\[(.*?)\]')
def _translator(match, definitions):
    d = definitions[match.group(1)]
    if d:
        return '({0})'.format(d)
    else:
        return ''
def expression_substitute(expr, definitions):
    translator = partial(_translator, definitions = definitions)
    return _finder.sub(translator, expr)


# _property_regex is used to find properties in expression strings
_property_regex = re.compile('[A-Za-z_]\w*(?!\w*\s*\()')

def negated(expression):
    """Returns a negated version of the expression.

    Args:
        expression: The expression to negate

    Returns:
        A negated version of the expression.
    """
    return '!({0})'.format(expression)


def variable_negated(expression, variable):
    """Negates all instances of the specified variable within the expression.

    Args:
        expression: The expression string
        variable: The variable name

    Returns:
        A version of the expression with instances of the specified variable
        negated.
    """
    # Define a simple function to do our negation
    def negator(match):
        # Grab the match group
        match_group = match.group(0)

        # Negate accordingly
        if match_group == variable:
            return '!({0})'.format(match_group)
        return match_group

    # Return an expression with all instances of this particular variable
    # negated
    return _property_regex.sub(negator, expression)

def variable_substituted(expression, variable, substitution):
    """Substitute all instances of the specified variable within the
    expression.

    Args:
        expression: The expression string
        variable: The variable name
        substitution: The expression to substitute the variable with

    Returns:
        A version of the expression with instances of the specified variable
        substituted.
    """
    # Return an expression with all instances of this particular variable
    # negated
    return re.sub(variable, substitution, expression)


def _combined(expressions, operator):
    """Private method to handle expression composition with a binary infix
    operator.

    Args:
        expressions: An iterable of expressions
        operator: The binary infix operator string with which to combine the
            expressions

    Returns:
        The combined expression string.
    """
    # Wrap expressions in parens if number of expressions is larger than 1.
    # Exclude empty expressions.
    if len(expressions) > 1:
        wrap_expr = ['({0})'.format(e) for e in expressions if e]
    else:
        wrap_expr = expressions

    # Join expressions if number of expressions is larger than 1
    if len(wrap_expr) > 1:
        return '({0})'.format(' {0} '.format(operator).join(wrap_expr))
    elif len(wrap_expr) == 1:
        return wrap_expr[0]
    else:
        return ''


def added(*expressions):
    """Returns the added expression adding multiple expressions.

    Args:
        *expressions: The expressions to combine

    Returns:
        The combined expression string.
    """
    return _combined(expressions, '+')


def subtracted(*expressions):
    """Returns the expression subtracting multiple expressions.

    Args:
        *expressions: The expressions to combine

    Returns:
        The combined expression string.
    """
    return _combined(expressions, '-')


def multiplied(*expressions):
    """Returns the multipled expression combing multiple expressions.

    Args:
        *expressions: The expressions to combine

    Returns:
        The combined expression string.
    """
    return _combined(expressions, '*')


def divided(*expressions):
    """Returns the expression dividing expressions using the '/' division
    operator.

    Args:
        *expressions: The expressions to combine

    Returns:
        The combined expression string.
    """
    return _combined(expressions, '/')


def floor_divided(*expressions):
    """Returns the expression dividing expressions using the '//' floor
    division operator.

    Args:
        *expressions: The expressions to combine

    Returns:
        The combined expression string.
    """
    return _combined(expressions, '//')


def anded(*expressions):
    """Returns the 'and' expression combining multiple expressions.

    Args:
        *expressions: The expressions to combine

    Returns:
        The combined expression string.
    """
    return _combined(expressions, '&&')


def ored(*expressions):
    """Returns the 'or' expression combining multiple expressions.

    Args:
        *expressions: The expressions to combine

    Returns:
        The combined expression string.
    """
    return _combined(expressions, '||')


def xored(*expressions):
    """Returns the 'xor' expression combining multiple expressions.

    Args:
        *expressions: The expressions to combine

    Returns:
        The combined expression string.
    """
    return _combined(expressions, '^')
