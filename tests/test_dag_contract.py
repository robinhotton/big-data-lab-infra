"""Contrat des DAGs — sans Airflow installé.

Ces tests ne **parse** pas les DAGs avec le scheduler (ce qui exigerait
Airflow + provider Amazon dans l'environnement de test). Ils vérifient que
chaque fichier de DAG reste syntaxiquement valide et conserve les invariants
du lab — c'est le garde-fou « on a cassé un TP sans s'en rendre compte ».

Si `apache-airflow` est installé, un test plus complet se lance : import
réel du module DAG.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

DAGS_DIR = Path(__file__).resolve().parent.parent / "airflow" / "dags"
DAG_FILES = sorted(DAGS_DIR.glob("*.py"))


def test_dags_directory_not_empty():
    assert DAG_FILES, "aucun DAG trouvé dans airflow/dags/ — le volume mount est-il bon ?"


@pytest.mark.parametrize("path", DAG_FILES, ids=lambda p: p.name)
def test_dag_syntax_valid(path: Path):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


@pytest.mark.parametrize("path", DAG_FILES, ids=lambda p: p.name)
def test_dag_declares_dag_id(path: Path):
    """Chaque DAG doit déclarer un `dag_id` littéral (pas dynamique) —
    c'est la clé d'affichage dans l'UI et dans la doc du TP."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    dag_ids = [
        kw.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "dag_id" and isinstance(kw.value, ast.Constant)
    ]
    assert dag_ids, f"{path.name}: aucun dag_id littéral trouvé"
    for dag_id in dag_ids:
        assert " " not in dag_id, f"dag_id invalide : {dag_id!r}"


@pytest.mark.parametrize("path", DAG_FILES, ids=lambda p: p.name)
def test_dag_uses_python_operator(path: Path):
    """Le lab utilise PythonOperator partout — détecte un remplacement
    accidentel par une macro/callable qui casserait les TP."""
    source = path.read_text(encoding="utf-8")
    assert "PythonOperator" in source, f"{path.name}: plus de PythonOperator"


# --- Import réel (uniquement si Airflow est installé) ----------------------


@pytest.mark.parametrize("path", DAG_FILES, ids=lambda p: p.name)
def test_dag_imports_with_airflow_if_available(path: Path, monkeypatch):
    pytest.importorskip("airflow")
    pytest.importorskip("airflow.providers.amazon")

    import importlib.util
    import sys

    # Le DAG fait `from config/extract/...` après sys.path.insert("/opt/airflow/src") :
    # on reproduit le montage du compose pour l'import hors conteneur.
    src_dir = str(DAGS_DIR.parent / "src")  # airflow/src
    monkeypatch.syspath_prepend(src_dir)

    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(path.stem, None)
