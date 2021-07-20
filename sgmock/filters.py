from datetime import datetime

from ._vendor.six import string_types
from .exceptions import Fault, MockError

_filters = {}


def match_types(a, b):
    if isinstance(a, datetime) and isinstance(b, string_types):
        return a.strftime('%Y-%m-%dT%H:%M:%SZ'), b
    if isinstance(a, string_types) and isinstance(b, datetime):
        return a, b.strftime('%Y-%m-%dT%H:%M:%SZ')
    else:
        return a, b


def And(filters):
    def _And(entity):
        return all(f(entity) for f in filters)
    return _And

def Or(filters):
    def _Or(entity):
        return any(f(entity) for f in filters)
    return _Or



def _compile_filters(filters):

    if isinstance(filters, dict):
        try:
            # New style
            op = filters['logical_operator']
            conditions = filters['conditions']
        except KeyError:
            # Old style
            op = filters.get('filter_operator', 'and')
            conditions = filters['filters']
    else:
        op = 'and'
        conditions = filters

    # While the documentation for shotgun_api complex filters describes the
    # use of `filter_operator` being one of `"any"` or `"all"` (the default),
    # the actual Shotgun server accepts a `logical_operator` of `'or'` or `'and'`
    # (respectively), and `shotgun_api3` actually supports both. And so we do
    # as well.
    # See: http://developer.shotgunsoftware.com/python-api/reference.html#complex-filters
    # See https://github.com/shotgunsoftware/python-api/blob/b13dd5d03b6b3c7bb946f77a9eaff7c3dc7ff324/shotgun_api3/shotgun.py#L4045-L4062
    if op in ('any', 'or'):
        op_cls = Or
    elif op in ('all', 'and'):
        op_cls = And
    else:
        raise ValueError("Invalid filter_operator {}".format(op))

    return op_cls([_compile_condition(f) for f in conditions])


def _compile_condition(condition):

    if isinstance(condition, dict):
        if 'filter_operator' in condition:
            return _compile_filters(condition)

        op_name = condition['relation']
        field = condition['path']
        values = condition['values']

    elif len(condition) == 3 and isinstance(condition[2], (list, tuple)):
        field, op_name, values = condition
    else:
        field = condition[0]
        op_name = condition[1]
        values = condition[2:]

    op_cls = _filters.get(op_name)
    if not op_cls:
        raise MockError('unknown filter relation %r' % op_name)
    return op_cls(field, *values)


def filter_entities(filters, entities):
    compiled = _compile_filters(filters)
    return (e for e in entities if compiled(e))



def NotWrap(cls):
    class _Not(object):
        def __init__(self, *args):
            self.filter = cls(*args)
        def __call__(self, entity):
            return not self.filter(entity)
    return _Not


def register(*names, **kwargs):
    wrap = kwargs.pop('wrap', None)
    def _register(cls):
        for name in names:
            _filters[name] = wrap(cls) if wrap else cls
        return cls
    return _register


class ScalarFilter(object):

    def __init__(self, field, value):
        self.field = field
        self.value = value

    def __call__(self, entity):
        value, other = match_types(self.value, entity.get(self.field))
        return self.test(value, other)

    def test(self, value, field):
        raise NotImplementedError()


@register('is')
@register('is_not', wrap=NotWrap)
class IsFilter(ScalarFilter):

    def test(self, value, field):
        if isinstance(value, dict):
            return (
                value.get('type') == (field or {}).get('type') and
                value.get('id') == (field or {}).get('id')
            )
        else:
            return value == field


@register('in')
@register('not_in', wrap=NotWrap)
class InFilter(object):

    def __init__(self, field, *values):
        self.field = field
        self.values = set(values)

    def __call__(self, entity):
        return entity.get(self.field) in self.values


@register('less_than')
class LessThanFilter(ScalarFilter):
    def test(self, value, field):
        return field < value

@register('greater_than')
class LessThanFilter(ScalarFilter):
    def test(self, value, field):
        return field > value


@register('starts_with')
class StartsWithFilter(ScalarFilter):

    def test(self, value, field):
        return field.startswith(value)


@register('ends_with')
class EndsWithFilter(ScalarFilter):

    def test(self, value, field):
        return field.endswith(value)
