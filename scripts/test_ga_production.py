"""Tests for the standalone SmartBiz production Genetic Algorithm."""

import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parent))

from scripts.ga_solver import genetic_search, recommend_all
from scripts.ucs_production import ProductionOption


def test_genetic_search_returns_empty_plan_when_stock_meets_target():
    result = genetic_search(10, 10, [ProductionOption(5, 20)], seed=1)

    assert result == ([], 0)


def test_genetic_search_returns_none_when_target_is_unreachable():
    result = genetic_search(0, 10, [], seed=1)

    assert result is None


def test_genetic_search_returns_a_feasible_batch_sequence():
    options = [ProductionOption(0, 0), ProductionOption(4, 10), ProductionOption(6, 15)]
    result = genetic_search(0, 10, options, seed=7)

    assert result is not None
    path, total_cost = result
    assert path
    assert sum(decision.produced_units for decision in path) >= 10
    assert all(decision.produced_units > 0 for decision in path)
    assert sum(decision.cost for decision in path) == total_cost


def test_genetic_search_is_reproducible_with_same_seed():
    options = [ProductionOption(4, 10), ProductionOption(6, 15), ProductionOption(10, 40)]
    settings = {"population_size": 20, "generations": 30, "seed": 123}

    first = genetic_search(0, 10, options, **settings)
    second = genetic_search(0, 10, options, **settings)

    assert first == second


@pytest.mark.parametrize(
    "settings",
    [
        {"population_size": 1},
        {"generations": -1},
        {"tournament_size": 0},
        {"elite_count": 0},
        {"mutation_rate": 1.1},
    ],
)
def test_genetic_search_rejects_invalid_parameters(settings):
    with pytest.raises(ValueError):
        genetic_search(0, 10, [ProductionOption(5, 10)], **settings)


def test_recommend_all_uses_existing_dataset_schema(tmp_path):
    tables = {
        "products": [
            {
                "product_id": "P001",
                "product_name": "Test Product",
                "initial_stock": 10,
            }
        ],
        "production_options": [
            {
                "product_id": "P001",
                "units_produced": 5,
                "production_cost": 20,
            }
        ],
        "inventory_history": [
            {"product_id": "P001", "quantity_change": 2},
        ],
    }
    for table_name, records in tables.items():
        (tmp_path / f"{table_name}.json").write_text(
            json.dumps(records), encoding="utf-8"
        )

    result = recommend_all(
        tmp_path,
        population_size=10,
        generations=5,
        seed=5,
    )

    assert result == [
        {
            "product_id": "P001",
            "product_name": "Test Product",
            "current_stock": 2,
            "target_stock": 10,
            "production_units": 10,
            "batch_count": 2,
            "total_cost": 40,
        }
    ]


def test_recommend_all_can_filter_a_single_product(tmp_path):
    products = [
        {"product_id": "P001", "product_name": "Product A", "initial_stock": 5},
        {"product_id": "P002", "product_name": "Product B", "initial_stock": 5},
    ]
    options = [
        {"product_id": product["product_id"], "units_produced": 5, "production_cost": 10}
        for product in products
    ]
    inventory = [
        {"product_id": product["product_id"], "quantity_change": 0}
        for product in products
    ]
    tables = {
        "products": products,
        "production_options": options,
        "inventory_history": inventory,
    }
    for table_name, records in tables.items():
        (tmp_path / f"{table_name}.json").write_text(
            json.dumps(records), encoding="utf-8"
        )

    result = recommend_all(
        tmp_path,
        product_id="P002",
        population_size=10,
        generations=5,
        seed=5,
    )

    assert [item["product_id"] for item in result] == ["P002"]