"""
Defines the Location  widget which allows changing the href of the window.
"""

import urllib.parse as urlparse

import param

from ..models.location import Location as _BkLocation
from ..reactive import Syncable
from ..util import parse_query
from .state import state


class Location(Syncable):
    """
    The Location component can be made available in a server context
    to provide read and write access to the URL components in the
    browser.
    """

    href = param.String(readonly=True, doc="""
        The full url, e.g. 'https://localhost:80?color=blue#interact'""")

    hostname = param.String(readonly=True, doc="""
        hostname in window.location e.g. 'panel.holoviz.org'""")

    pathname = param.String(regex=r"^$|[\/].*$", doc="""
        pathname in window.location e.g. '/user_guide/Interact.html'""")

    protocol = param.String(readonly=True, doc="""
        protocol in window.location e.g. 'http:' or 'https:'""")

    port = param.String(readonly=True, doc="""
        port in window.location e.g. '80'""")

    search = param.String(regex=r"^$|\?", doc="""
        search in window.location e.g. '?color=blue'""")

    hash = param.String(regex=r"^$|#", doc="""
        hash in window.location e.g. '#interact'""")

    reload = param.Boolean(default=False, doc="""
        Reload the page when the location is updated. For multipage
        apps this should be set to True, For single page apps this
        should be set to False""")

    # Mapping from parameter name to bokeh model property name
    _rename = {"name": None}

    def __init__(self, **params):
        super(Location, self).__init__(**params)
        self._synced = []
        self._syncing = False
        self.param.watch(self._update_synced, ['search'])
        self.param.watch(self._onload, ['href'])

    def _onload(self, event):
        # Skip if href was not previously empty or not in a server context
        if event.old or not state.curdoc: 
            return
        for cb in state._onload.get(state.curdoc, []):
            cb()

    def _get_model(self, doc, root=None, parent=None, comm=None):
        model = _BkLocation(**self._process_param_change(self._init_properties()))
        root = root or model
        values = dict(self.param.get_param_values())
        properties = list(self._process_param_change(values))
        self._models[root.ref['id']] = (model, parent)
        self._link_props(model, properties, doc, root, comm)
        return model

    def _get_root(self, doc=None, comm=None):
        root = self._get_model(doc, comm=comm)
        ref = root.ref['id']
        state._views[ref] = (self, root, doc, comm)
        return root

    def _update_synced(self, event=None):
        if self._syncing:
            return
        query_params = self.query_params
        for p, parameters, _ in self._synced:
            mapping = {v: k for k, v in parameters.items()}
            p.param.set_param(**{mapping[k]: v for k, v in query_params.items()
                                 if k in mapping})

    def _update_query(self, *events, query=None):
        if self._syncing:
            return
        query = query or {}
        for e in events:
            matches = [ps for o, ps, _ in self._synced if o in (e.cls, e.obj)]
            if not matches:
                continue
            query[matches[0][e.name]] = e.new
        self._syncing = True
        try:
            self.update_query(**{k: v for k, v in query.items() if v is not None})
        finally:
            self._syncing = False

    @property
    def query_params(self):
        return parse_query(self.search)

    def update_query(self, **kwargs):
        query = self.query_params
        query.update(kwargs)
        self.search = '?' + urlparse.urlencode(query)

    def sync(self, parameterized, parameters=None):
        """
        Syncs the parameters of a Parameterized object with the query
        parameters in the URL.
        
        Arguments
        ---------
        parameterized (param.Parameterized):
          The Parameterized object to sync query parameters with
        parameters (list or dict):
          A list or dictionary specifying parameters to sync. 
          If a dictionary is supplied it should define a mapping from
          the Parameterized's parameteres to the names of the query
          parameters.
        """
        parameters = parameters or [p for p in parameterized.param if p != 'name']
        if not isinstance(parameters, dict):
            parameters = dict(zip(parameters, parameters))
        watcher = parameterized.param.watch(self._update_query, list(parameters))
        self._synced.append((parameterized, parameters, watcher))
        self._update_synced()
        self._update_query(query={v: getattr(parameterized, k)
                                  for k, v in parameters.items()})

    def unsync(self, parameterized):
        """
        Unsyncs a Parameterized object which has been previous synced
        with the Location component.
        
        Arguments
        ---------
        parameterized (param.Parameterized):
          The Parameterized object to sync query parameters with
        """
        matches = [s for s in self._synced if s[0] is parameterized]
        if not matches:
            ptype = type(parameterized)
            raise ValueError(f"Cannot unsync {ptype} object since it "
                             "was never synced in the first place.")
        self._synced.remove(matches[0])
        parameterized.param.unwatch(matches[0][-1])
        
        
