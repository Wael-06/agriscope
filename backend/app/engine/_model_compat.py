from __future__ import annotations


def ensure_legacy_sklearn_pickle_compat() -> None:
    """Allow older sklearn pickle artifacts to load under newer sklearn releases.

    Some legacy pipeline artifacts rely on private helper classes and attributes that were
    renamed or removed in newer sklearn versions. Registering tiny compatibility shims
    keeps the existing serialized models usable without retraining them.
    """
    try:
        from sklearn.compose import _column_transformer as column_transformer
        from sklearn.impute import SimpleImputer
    except Exception:
        return

    if not hasattr(column_transformer, "_RemainderColsList"):
        class _RemainderColsList(list):
            pass

        column_transformer._RemainderColsList = _RemainderColsList

    if not hasattr(column_transformer, "_RemainderCols"):
        class _RemainderCols(list):
            pass

        column_transformer._RemainderCols = _RemainderCols

    if not hasattr(SimpleImputer, "_fill_dtype"):
        SimpleImputer._fill_dtype = property(lambda self: self._fit_dtype)
