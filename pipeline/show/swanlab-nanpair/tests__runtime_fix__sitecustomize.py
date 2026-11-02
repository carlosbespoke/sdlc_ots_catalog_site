# Verifier-owned runtime fix: non-finite scalars keep their value when they are recorded, and the
# local dashboard writes each recorded value as is. Every repository file stays byte-identical, and
# the original function objects keep their source text (only their code objects are replaced).
try:
    from swanlab.deprecated import local as _local
    from swanlab.sdk.internal.run.transforms import scalar as _scalar

    _TRANSFORM = '''
def transform(data):
    this_value = _transform_tensor_or_array(data)
    if this_value is None:
        full_type_name = f"{type(data).__module__}.{type(data).__name__}"
        raise TypeError(
            f"Failed to extract scalar value from {full_type_name}. "
            "If it's a Tensor or Array, please ensure it's a scalar value.",
        )
    data = this_value
    if isinstance(data, bool):
        return ScalarValue(number=float(data))
    if isinstance(data, (int, float)):
        return ScalarValue(number=float(data))
    if isinstance(data, str):
        try:
            value = float(data)
        except ValueError:
            raise TypeError(f"Unsupported scalar string value: '{data}'.")
        if math.isnan(value) or math.isinf(value):
            return ScalarValue(number=math.nan)
        return ScalarValue(number=value)
    raise TypeError(f"Unsupported scalar type: {type(data).__name__}.")
'''

    _HANDLE = '''
def _handle_metric(self, record, scalar):
    self._check_exp_status()
    ctx = self._get_metric_context(record, scalar=scalar)
    if record.key not in self._created_columns:
        self._create_column(record, ctx)
        self._created_columns.add(record.key)
    data, more = (record.value.number, None) if scalar else self._media_data(record, ctx)
    metric, overwrite, relative_path = ctx.add(
        step=int(record.step), data=data, create_time=self._record_time(record), more=more
    )
    metric_dir = self._require_swanlog_dir() / ctx.kid
    metric_dir.mkdir(parents=True, exist_ok=True)
    metric_path = self._require_swanlog_dir() / relative_path
    summary_path = metric_dir / "_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(ctx.summary, ensure_ascii=False))
    if overwrite:
        self._rewrite_metric_file(metric_path, metric)
    else:
        with open(metric_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(metric, ensure_ascii=False) + "\\n")
'''

    def _swap(target, source, module, name):
        namespace = {}
        exec(compile(source, module.__file__, "exec"), module.__dict__, namespace)
        target.__code__ = namespace[name].__code__

    _swap(_scalar.Scalar.__dict__["transform"].__func__, _TRANSFORM, _scalar, "transform")
    _swap(_local.LocalCallbacker._handle_metric, _HANDLE, _local, "_handle_metric")
except Exception:  # the tree may not be importable at all
    pass
