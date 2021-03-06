import globals
from lepl import *
from bisect import bisect_left
import logging


""" The following class definitions are used to aid in the construction of the
    Abstract Syntax Tree from the expression.  For example, they allow simple tests
    such as isinstance(exprtree, Identfier).  See expr_evaluate(exprtree, context). """

class Identifier(List):
    pass


class Number(List):
    pass


class Add(List):
    pass


class Sub(List):
    pass


class Mul(List):
    pass


class Div(List):
    pass


class FunctionCall(List):
    pass

""" Grammar rules used by the lepl module.  See http://www.acooke.org/lepl/ for more info """
my_Identifier = Token(r'[a-zA-Z_][a-zA-Z_0-9]*') > Identifier
symbol = Token('[^0-9a-zA-Z \t\r\n]')
my_Value = Token(UnsignedReal())
my_Number = Optional(symbol('-')) + my_Value > Number
group2 = Delayed()
my_Expr = Delayed()


# first layer, most tightly grouped, is parens and numbers
parens = ~symbol('(') & my_Expr & ~symbol(')')
my_Function = my_Identifier & parens > FunctionCall
group1 = my_Function | parens | my_Number | my_Identifier


# second layer, next most tightly grouped, is multiplication
my_Mul = group1 & ~symbol('*') & group2 > Mul
my_Div = group1 & ~symbol('/') & group2 > Div
group2 += my_Mul | my_Div | group1

# third layer, least tightly grouped, is addition
my_Add = group2 & ~symbol('+') & my_Expr > Add
my_Sub = group2 & ~symbol('-') & my_Expr > Sub
my_Expr += my_Add | my_Sub | group2


def parse_expr(expr, context):
    """ Wrapper function to the entry lepl parse function.
        If manage to parse return Abstract Syntax Tree, otherwise send message over web socket to
        the web browser and return the empty string. """
    try:
        result = my_Expr.parse(expr)
        return result
    except:
        logging.debug("Could not parse the expression " + str(expr))
        return ''

def series_by_name(seriesname, context):
    keysDictionary = {'keys': [context['file'], context['bucket']]}
    file = context['file']
    bucket = context['bucket']
    data = {}
    try:
        data = globals.stats[file][bucket]
    except:
        return []
    result = []
    for x in data:
        try:
            result.append([x['localtime'], x[seriesname]])
        except:
            return []
    return result


def multiplying(op1, op2):
    if isinstance(op1, list) and not isinstance(op2, list):
        for x in op1:
            x[1] = x[1] * op2
        return op1
    elif isinstance(op2, list) and not isinstance(op1, list):
        for x in op2:
            x[1] = x[1] * op1
        return op2
    else:
        if len(op1) != len(op2):
            print('Error multiplying: lengths not equal.  See function multiplying(op1, op2)')
            return []
        else:
            for x in range(len(op1)):
                op1[x][1] = op1[x][1] * op2[x][1]
            return op1


def dividing(op1, op2):
    if isinstance(op1, list) and not isinstance(op2, list):
        for x in range(len(op1)):
            if op2 == 0:
                op1[x][1] = None
            else:
                op1[x][1] = op1[x][1] / op2
        return op1
    elif isinstance(op2, list) and isinstance(op1, list):
        if len(op1) != len(op2):
            print('Error dividing: lengths not equal.  See function dividing(op1, op2)')
            return []
        else:
            for x in range(len(op1)):
                if op2[x][1] == 0:
                    op1[x][1] = None
                else:
                    op1[x][1] = op1[x][1] / op2[x][1]
            return op1
    else:
        print('Error dividing: dividing number by a list.  See function dividing(op1, op2)')
        return []


def adding(op1, op2):
    if isinstance(op1, list) and not isinstance(op2, list):
        for x in op1:
            x[1] = x[1] + op2
        return op1
    if isinstance(op2, list) and not isinstance(op1, list):
        for x in op2:
            x[1] = x[1] + op1
        return op2
    else:
        if len(op1) != len(op2):
            print('Error in adding function: lengths not equal')
            return []
        else:
            for x in range(len(op1)):
                op1[x][1] = op1[x][1] + op2[x][1]
            return op1


def subtracting(op1, op2):
    if isinstance(op1, list) and not isinstance(op2, list):
        for x in op1:
            x[1] = x[1] - op2
        return op1
    elif isinstance(op2, list) and isinstance(op1, list):
        if len(op1) != len(op2):
            print('Error in subtracting function: lengths not equal')
            return []
        else:
            for x in range(len(op1)):
                op1[x][1] = op1[x][1] - op2[x][1]
            return op1
    else:
        print('Error in subtracting function: subtracting list from a number')
        return []


def derivative(f):
    """ Function that returns the (approx) derivative of function f. """
    def df(x, h=0.1e-4):
        return (f(x + h / 2) - f(x - h / 2)) / h
    return df


def binary_search(a, x, lo=0, hi=None):
    hi = hi if hi is not None else len(a)
    pos = bisect_left(a, x, lo, hi)
    if pos == 0 or pos == hi or (a[pos] >= x and a[pos - 1] <= x):
        return pos
    else:
        return -1


def searchsorted(xin, xout):
    xin.sort()
    result = binary_search(xin, xout)
    return result


def interpolate(derivseries, interpargs):
    xin = []
    yin = []
    for p in derivseries:
        xin.append(p[0])
        yin.append(p[1])
    lenxin = len(xin)

    def inter(xout):
        i1 = searchsorted(xin, xout)
        #s1 = numpy.searchsorted(xin, xout)
        # if i1 != s1:
        #  print("s1 = " + str(s1) + " il = " + str(i1))
        if i1 == 0:
            i1 = 1
        if i1 == lenxin:
            i1 = lenxin - 1
        x0 = xin[i1 - 1]
        x1 = xin[i1]
        y0 = yin[i1 - 1]
        y1 = yin[i1]
        if interpargs == 'linear':
            return (xout - x0) / (x1 - x0) * (y1 - y0) + y0
    return inter


def derivativewrapper(pointseries, interpargs):
    derivseries = []
    # Remove all those that have null as second argument
    for x in pointseries:
        if x[1] != None:
            derivseries.append(x)
    # Return the interpolate function
    inter = interpolate(derivseries, interpargs)
    # Return the first derivative function applied to the interpolate function
    dg = derivative(inter)
    result = []
    for x in pointseries:
        newx = [x[0], dg(x[0] + 0.5)]
        result.append(newx)
    return result


def moving_average(pointseries, window):
    """ Function for calculating the moving average.
        The Python module Numpy can be used to calulate the moving average
        (using the convolve function), but Numpy is not compatible with pypy and
        so has not been used. """
    smoothed = []
    for n in range(len(pointseries)):
        rangestart = n - window
        rangeend = n + window + 1
        samples = []
        if rangestart < 0:
            rangestart = 0
            samples.append(None)
        if rangeend > len(pointseries):
            rangeend = len(pointseries)
            samples.append(None)
        for x in range(rangestart, rangeend):
            samples.append(pointseries[x][1])
        orig = pointseries[n]
        # in clojure code also check that n - window - 1 < 0.
        # Don't know why - does not appear to be required. Bug?
        if None in samples:
            result = [orig[0], None]
        else:
            numofsamples = len(samples)
            samplestotal = sum(samples)
            result = [orig[0], float(samplestotal) / float(numofsamples)]
        smoothed.append(result)
    return smoothed


def expr_fun_table(fname, seriesname, context):
    """ Provides support for calling functions.  Currently only rate is supported.  """
    if fname[0] == 'rate':
        # Get the uptime from the stats
        uptime = series_by_name('uptime', context)
        # Calculate the moving average of uptime
        movingaverage = moving_average(uptime, context['smoothing-window'])
        # Calculate the derivative of uptime
        derivativeresult = derivativewrapper(movingaverage, 'linear')
        # Get the series we are calculating the rate for
        series = series_by_name(seriesname[0], context)
        # Calculate the moving average of the series
        seriesmovingaverage = moving_average(series, context['smoothing-window'])
        # Calculate the derivative of the series
        seriesderivativeresult = derivativewrapper(seriesmovingaverage, 'linear')
        
        if len(derivativeresult) != len(seriesderivativeresult):
            print('Error: length of uptime derivative result != length of series derivative result. \
                   See function expr_fun_table(fname, seriesname, context).')
            return []
        
        result = []
        # Iterate through all the results for the derivative of uptime.
        # If any of the derivative results are negative replace them with None.
        for x in range(len(derivativeresult)):
            if derivativeresult[x][1] < 0:
                result.append([seriesderivativeresult[x][0], None])
            else:
                result.append(seriesderivativeresult[x])
        return result

    else:
        print('Error do not recognise function in expr_fun_table(fname, seriesname, context)')
        return []


def expr_evaluate(exprtree, context):
    """ Recursive function for performing traversal of Abstract Syntax Tree. """
    if isinstance(exprtree, Number):
        return float(exprtree[0])
    elif isinstance(exprtree, Identifier):
        return series_by_name(exprtree[0], context)
    elif isinstance(exprtree, FunctionCall):
        return expr_fun_table(exprtree[0], exprtree[1], context)
    elif isinstance(exprtree, Mul):
        op1 = expr_evaluate(exprtree[0], context)
        op2 = expr_evaluate(exprtree[1], context)
        return multiplying(op1, op2)
    elif isinstance(exprtree, Div):
        op1 = expr_evaluate(exprtree[0], context)
        op2 = expr_evaluate(exprtree[1], context)
        return dividing(op1, op2)
    elif isinstance(exprtree, Sub):
        op1 = expr_evaluate(exprtree[0], context)
        op2 = expr_evaluate(exprtree[1], context)
        return subtracting(op1, op2)
    elif isinstance(exprtree, Add):
        op1 = expr_evaluate(exprtree[0], context)
        op2 = expr_evaluate(exprtree[1], context)
        return adding(op1, op2)


def expr_eval_string(expr, contextDictionary):
    """ wrapper function for fully parsing the query expression, then
        evaluating the expression returning the data.  If expression cannot
        be parsed or there is no data then the empty list is returned. """
    # Remove whitespace from start & end of the string.
    # Can't see whenever this is required however in the original mortimer.
    expr = expr.strip()
    # Uses the lepl module to parse the expression into an Abstract Syntax Tree.
    parsedExpression = parse_expr(expr, contextDictionary)
    result = []
    # If successfully parsed the expression try to evaluate it.
    if parsedExpression != '':
        result = expr_evaluate(parsedExpression[0], contextDictionary)
    return result
