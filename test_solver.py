"""Module test_solver.py: Suite pengujian otomatis untuk solver.py menggunakan pytest."""

import pytest
import json
from pathlib import Path
from solver import (
    CSPSolver,
    Variable,
    Constraint,
    UnsatisfiableConstraintError,
    DatasetLoader,
    SmartBizOptimizer,
)


@pytest.fixture
def mock_dataset_dir(tmp_path):
    """Fixture untuk membuat dataset JSON tiruan sederhana."""
    data_dir = tmp_path / "smartbiz_json"
    data_dir.mkdir()

    products = [{"id": 1, "name": "Brownies Toba", "production_cost": 5000.0}]
    ingredients = [{"id": 101, "name": "Tepung Terigu", "cost_per_unit": 2000.0, "current_stock": 2.0}]
    recipes = [{"product_id": 1, "ingredient_id": 101, "quantity": 0.5}]
    options = [{"batch_size": 0}, {"batch_size": 5}, {"batch_size": 10}]

    (data_dir / "products.json").write_text(json.dumps(products))
    (data_dir / "ingredients.json").write_text(json.dumps(ingredients))
    (data_dir / "product_recipes.json").write_text(json.dumps(recipes))
    (data_dir / "production_options.json").write_text(json.dumps(options))

    return str(data_dir)


def test_dataset_loader(mock_dataset_dir):
    """Pengujian keterbacaan dataset oleh DatasetLoader."""
    loader = DatasetLoader(mock_dataset_dir)
    data = loader.load_all_data()

    assert "products" in data
    assert len(data["products"]) == 1
    assert data["products"][0]["name"] == "Brownies Toba"


def test_smartbiz_optimizer_success(mock_dataset_dir):
    """Menguji eksekusi sukses optimasi dengan dataset valid."""
    optimizer = SmartBizOptimizer(data_dir=mock_dataset_dir, budget_limit=100000.0)
    solution = optimizer.build_and_solve()

    assert "production" in solution
    assert "restock" in solution
    assert 1 in solution["production"]
    assert 101 in solution["restock"]


def test_unsatisfiable_budget_edge_case(mock_dataset_dir):
    """Kasus Ekstrem: Anggaran bernilai negatif (-1.0) sehingga dipastikan melanggar batasan."""
    optimizer = SmartBizOptimizer(data_dir=mock_dataset_dir, budget_limit=-1.0)

    with pytest.raises(UnsatisfiableConstraintError):
        optimizer.build_and_solve()


def test_empty_domain_edge_case():
    """Kasus Ekstrem: Variabel dengan domain kosong langsung memicu exception."""
    v1 = Variable("v1", "production")
    domains = {v1: []}
    solver = CSPSolver(variables=[v1], domains=domains, constraints=[])

    with pytest.raises(UnsatisfiableConstraintError):
        solver.solve()


def test_real_dataset_integration():
    """Menguji modul solver dengan folder dataset 'smartbiz_json' yang sesungguhnya."""
    dataset_path = Path("smartbiz_json")
    if dataset_path.exists():
        optimizer = SmartBizOptimizer(data_dir="smartbiz_json", budget_limit=1000000.0)
        solution = optimizer.build_and_solve()
        assert solution is not None
        assert "production" in solution