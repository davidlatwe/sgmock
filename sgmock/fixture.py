_required = object()


class Fixture(object):
    
    def __init__(self, shotgun):
        self.shotgun = shotgun
        self.created = []
    
    def __getattr__(self, name):
        if name[0].isupper():
            return _Creator(self, name)
        else:
            return getattr(self.shotgun, name)
            
    def create(self, *args, **kwargs):
        x = self.shotgun.create(*args, **kwargs)
        self.created.append((x['type'], x['id']))
        return x
        
    def delete_all(self):
        if not self.created:
            return
        self.shotgun.batch([dict(
            request_type='delete',
            entity_type=type_,
            entity_id=id_,
        ) for type_, id_ in reversed(self.created)])
        self.created = []
        
    def find_or_create(self, entity_type, datum=None, **kwargs):
        
        if datum and kwargs:
            raise ValueError('specify datum or kwargs')
        if kwargs:
            datum = [kwargs]
            is_single = True
        elif isinstance(datum, dict):
            datum = [datum]
            is_single = True
        else:
            is_single = False
        
        result = []
        for data in datum:
            filters = []
            for k, v in data.iteritems():
                filters.append((k, 'is', v))
            entity = self.shotgun.find_one(entity_type, filters, data.keys())
            if entity:
                result.append(entity)
                continue
            data = data.copy()
            data.pop('id', None)
            result.append(self.create(entity_type, data, data.keys()))
        
        return result[0] if is_single else result
    
    def default_steps(self):
        """Return a dict mapping short_names to entities for a default set of steps."""
        steps = {}
        for code in ('Client', 'Online', 'Roto', 'MM', 'Anm', 'FX',
            'Light', 'Comp', 'Art', 'Model', 'Rig', 'Surface'
        ):
            steps[code] = self.find_or_create('Step', dict(
                code=code,
                short_name=code))
        return steps


class _Creator(object):
    
    def __init__(self, fixture, entity_type, parent=None):
        self.fixture = fixture
        self.entity_type = entity_type
        self.parent = parent
        
    def __call__(self, *args, **kwargs):
        constructor = _entity_types.get(self.entity_type, _Entity)
        for name, default in constructor._argument_defaults:
            if name not in kwargs:
                if not args:
                    if default is _required:
                        raise TypeError('%s missing required %s' % (self.entity_type, name))
                    kwargs[name] = default
                else:
                    kwargs[name] = args[0]
                    args = args[1:]
        raw = self.fixture.create(self.entity_type, kwargs, kwargs.keys())
        return constructor(self.fixture, self.parent, raw)


class _Entity(dict):
    
    _argument_defaults = []
    _parent = None
    _backrefs = {}
    
    def __init__(self, fixture, parent, data):
        super(_Entity, self).__init__(data)
        self.fixture = fixture
        if parent:
        
            # Set any backrefs to our parent.
            self[parent._backrefs[self['type']]] = parent.minimal
            
            # Set the project if it is in our parent.
            if parent['type'] == 'Project':
                self['project'] = parent.minimal
            elif 'project' in parent:
                self['project'] = parent['project'].copy()
    
    def __getattr__(self, name):
        if name[0].isupper() and name in self._backrefs:
            return _Creator(self.fixture, name, self)
        raise AttributeError(name)
    
    @property
    def minimal(self):
        return dict(type=self['type'], id=self['id'])


class _Project(_Entity):
    _argument_defaults = [('name', _required)]
    _backrefs = {
        'Sequence': 'project',
        'Asset': 'project',
    }

class _Sequence(_Entity):
    _argument_defaults = [('code', _required)]
    _parent = 'project'
    _backrefs = {'Shot': 'sg_sequence'}

class _Shot(_Entity):
    _argument_defaults = [('code', _required)]
    _parent = 'sg_sequence'
    _backrefs = {'Task': 'entity'}

class _Task(_Entity):
    _argument_defaults = [('content', _required)]
    _parent = 'entity'

class _Step(_Entity):
    _argument_defaults = [('short_name', _required)]

class _Asset(_Entity):
    _argument_defaults = [('code', _required), ('sg_asset_type', 'Generic')]
    _parent = 'project'
    _backrefs = {'Task': 'entity'}



_entity_types = dict(
    (name[1:], value)
    for name, value in globals().iteritems()
    if isinstance(value, type) and issubclass(value, _Entity)
) 
