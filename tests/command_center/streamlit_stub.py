import sys
import types


class SessionState(dict):
    def __getattr__(self, name):
        return self.get(name)

    def __setattr__(self, name, value):
        self[name] = value


class DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _context_list(count: int):
    return [DummyContext() for _ in range(count)]


def _get_options(args, kwargs):
    if "options" in kwargs:
        return kwargs["options"]
    if len(args) >= 2:
        return args[1]
    return []


def build_streamlit_stub():
    st = types.ModuleType("streamlit")
    st.session_state = SessionState()
    st.sidebar = DummyContext()

    def columns(spec):
        count = spec if isinstance(spec, int) else len(spec)
        return _context_list(count)

    def tabs(names):
        return _context_list(len(names))

    def expander(*args, **kwargs):
        return DummyContext()

    def form(*args, **kwargs):
        return DummyContext()

    def container(*args, **kwargs):
        return DummyContext()

    def spinner(*args, **kwargs):
        return DummyContext()

    def selectbox(*args, **kwargs):
        options = _get_options(args, kwargs)
        index = kwargs.get("index", 0)
        if options:
            return options[index]
        return kwargs.get("value")

    def radio(*args, **kwargs):
        options = _get_options(args, kwargs)
        index = kwargs.get("index", 0)
        if options:
            return options[index]
        return kwargs.get("value")

    def multiselect(*args, **kwargs):
        default = kwargs.get("default")
        if default is None:
            return []
        return default

    def checkbox(*args, **kwargs):
        return kwargs.get("value", False)

    def toggle(*args, **kwargs):
        return kwargs.get("value", False)

    def button(*args, **kwargs):
        return False

    def form_submit_button(*args, **kwargs):
        return False

    def text_input(*args, **kwargs):
        return kwargs.get("value", "")

    def text_area(*args, **kwargs):
        return kwargs.get("value", "")

    def number_input(*args, **kwargs):
        if "value" in kwargs:
            return kwargs["value"]
        return kwargs.get("min_value", 0)

    def slider(*args, **kwargs):
        if "value" in kwargs:
            return kwargs["value"]
        return kwargs.get("min_value", 0)

    def date_input(*args, **kwargs):
        return kwargs.get("value")

    def file_uploader(*args, **kwargs):
        return None

    def cache_data(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def cache_clear():
        return None

    cache_data.clear = cache_clear

    # Attach functions
    st.columns = columns
    st.tabs = tabs
    st.expander = expander
    st.form = form
    st.container = container
    st.spinner = spinner
    st.selectbox = selectbox
    st.radio = radio
    st.multiselect = multiselect
    st.checkbox = checkbox
    st.toggle = toggle
    st.button = button
    st.form_submit_button = form_submit_button
    st.text_input = text_input
    st.text_area = text_area
    st.number_input = number_input
    st.slider = slider
    st.date_input = date_input
    st.file_uploader = file_uploader
    st.cache_data = cache_data

    def _noop(*args, **kwargs):
        return None

    for name in [
        "markdown",
        "write",
        "title",
        "header",
        "subheader",
        "caption",
        "info",
        "warning",
        "error",
        "success",
        "metric",
        "dataframe",
        "table",
        "plotly_chart",
        "altair_chart",
        "line_chart",
        "bar_chart",
        "json",
        "set_page_config",
        "stop",
        "rerun",
        "divider",
        "progress",
        "image",
    ]:
        setattr(st, name, _noop)

    return st


def install_streamlit_stub(monkeypatch):
    st = build_streamlit_stub()
    components_v1 = types.ModuleType("streamlit.components.v1")
    components_v1.html = lambda *args, **kwargs: None
    components_v1.iframe = lambda *args, **kwargs: None

    components_pkg = types.ModuleType("streamlit.components")
    components_pkg.v1 = components_v1
    st.components = components_pkg

    monkeypatch.setitem(sys.modules, "streamlit", st)
    monkeypatch.setitem(sys.modules, "streamlit.components", components_pkg)
    monkeypatch.setitem(sys.modules, "streamlit.components.v1", components_v1)
    return st
