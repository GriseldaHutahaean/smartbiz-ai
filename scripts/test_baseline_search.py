"""Tests for the SmartBiz baseline UCS production module.

This repository currently contains one implemented decision-support module:
Uniform Cost Search for production planning. The finance, inventory, and
forecasting features described in the SmartBiz README are not implemented yet,
so those requirements are reported as skipped instead of being faked.
"""

import sys
from pathlib import Path

import pytest

# Menambahkan folder scripts ke dalam path pencarian Python.
sys.path.append(str(Path(__file__).resolve().parent))

# pylint: disable=wrong-import-position
from ucs_production import (
    Decision,
    ProductionOption,
    build_graph,
    uniform_cost_search,
)
from ucs_dataset import recommend_all


@pytest.fixture
def product_scenarios() -> dict[str, dict[str, object]]:
    """Scenario produk generik untuk pengujian SmartBiz berdasarkan data kontrol."""
    return {
        "Product A": {
            "start_stock": 0,
            "demand": 10,
            "options": [ProductionOption(5, 30), ProductionOption(10, 70)],
        },
        "Product B": {
            "start_stock": 5,
            "demand": 20,
            "options": [
                ProductionOption(5, 25_000),
                ProductionOption(10, 50_000),
                ProductionOption(15, 75_000),
            ],
        },
        "Product C": {
            "start_stock": 0,
            "demand": 15,
            "options": [
                ProductionOption(5, 12),
                ProductionOption(10, 19),
                ProductionOption(15, 30),
            ],
        },
        "Product D": {
            "start_stock": 0,
            "demand": 9,
            "options": [ProductionOption(4, 0), ProductionOption(10, 1)],
        },
        "Product E": {
            "start_stock": 0,
            "demand": 12,
            "options": [ProductionOption(3, 2), ProductionOption(8, 7)],
        },
    }


@pytest.mark.parametrize(
    ("start_stock", "demand", "options", "expected_graph"),
    [
        pytest.param(
            5,
            20,
            [ProductionOption(5, 25_000), ProductionOption(10, 50_000)],
            {
                5: [
                    Decision(5, 10, 5, 25_000),
                    Decision(5, 15, 10, 50_000),
                ],
                10: [
                    Decision(10, 15, 5, 25_000),
                    Decision(10, 20, 10, 50_000),
                ],
                15: [
                    Decision(15, 20, 5, 25_000),
                    Decision(15, 25, 10, 50_000),
                ],
            },
            id="baseline-graph-expansion",
        ),
        pytest.param(
            0,
            10,
            [ProductionOption(5, 100), ProductionOption(10, 250)],
            {
                0: [Decision(0, 5, 5, 100), Decision(0, 10, 10, 250)],
                5: [Decision(5, 10, 5, 100), Decision(5, 15, 10, 250)],
            },
            id="multiple-options-and-goal-edge",
        ),
        pytest.param(
            7,
            7,
            [ProductionOption(3, 50)],
            {},
            id="start-stock-at-demand",
        ),
        pytest.param(0, 10, [], {0: []}, id="no-production-options"),
        pytest.param(
            0,
            1,
            [ProductionOption(0, 0)],
            {0: [Decision(0, 0, 0, 0)]},
            id="zero-unit-option-is-allowed-but-does-not-expand",
        ),
    ],
)
def test_build_graph_builds_expected_edges(start_stock, demand, options, expected_graph):
    """Graf harus merepresentasikan state stok dan keputusan produksi yang valid."""
    graph = build_graph(start_stock, demand, options)

    assert graph == expected_graph


@pytest.mark.parametrize(
    ("product_name", "start_stock", "demand", "options", "expected_cost", "expected_steps"),
    [
        pytest.param(
            "Product A",
            0,
            10,
            [ProductionOption(5, 30), ProductionOption(10, 70)],
            60,
            2,
            id="cheaper-indirect-path-beats-direct-expensive-path",
        ),
        pytest.param(
            "Product B",
            5,
            20,
            [
                ProductionOption(5, 25_000),
                ProductionOption(10, 50_000),
                ProductionOption(15, 75_000),
            ],
            75_000,
            1,
            id="baseline-production-scenario",
        ),
        pytest.param(
            "Product C",
            0,
            15,
            [ProductionOption(5, 12), ProductionOption(10, 19), ProductionOption(15, 30)],
            30,
            1,
            id="multiple-paths-requires-lowest-total-cost",
        ),
        pytest.param(
            "Product D",
            0,
            9,
            [ProductionOption(4, 0), ProductionOption(10, 1)],
            0,
            3,
            id="zero-cost-batch-still-chooses-cheapest-cumulative-path",
        ),
        pytest.param(
            "Product E",
            0,
            12,
            [ProductionOption(3, 2), ProductionOption(8, 7)],
            8,
            4,
            id="cumulative-cost-across-several-batches",
        ),
    ],
)
def test_uniform_cost_search_selects_lowest_cumulative_cost(
    product_name, start_stock, demand, options, expected_cost, expected_steps
):
    """UCS harus memilih jalur dengan total biaya kumulatif paling rendah."""
    graph = build_graph(start_stock, demand, options)
    result = uniform_cost_search(graph, start_stock, demand)

    assert result is not None, product_name
    path, total_cost = result
    assert total_cost == expected_cost, product_name
    assert sum(decision.cost for decision in path) == total_cost
    assert len(path) == expected_steps, product_name
    assert path[-1].to_stock >= demand


@pytest.mark.parametrize(
    ("start_stock", "demand", "options", "expected_cost", "expected_steps"),
    [
        pytest.param(10, 10, [ProductionOption(5, 20)], 0, 0, id="already-at-goal"),
        pytest.param(12, 10, [], 0, 0, id="start-stock-above-goal-no-options"),
        pytest.param(0, 10, [], None, None, id="unreachable-goal"),
    ],
)
def test_uniform_cost_search_handles_goal_and_unreachable_edges(
    start_stock, demand, options, expected_cost, expected_steps
):
    """Kondisi goal dan unreachable harus diperlakukan sesuai logika current implementation."""
    graph = build_graph(start_stock, demand, options)
    result = uniform_cost_search(graph, start_stock, demand)

    if expected_cost is None:
        assert result is None
        return

    assert result is not None
    path, total_cost = result
    assert total_cost == expected_cost
    assert len(path) == expected_steps


@pytest.mark.parametrize(
    ("units", "cost"),
    [(1, 1), (5, 25_000), (20, 125_000)],
)
def test_production_option_stores_units_and_cost(units, cost):
    option = ProductionOption(units=units, cost=cost)

    assert option.units == units
    assert option.cost == cost


@pytest.mark.parametrize(
    ("from_stock", "to_stock", "produced_units", "cost"),
    [(0, 5, 5, 25_000), (8, 18, 10, 40_000)],
)
def test_decision_stores_transition_and_cost(from_stock, to_stock, produced_units, cost):
    decision = Decision(
        from_stock=from_stock,
        to_stock=to_stock,
        produced_units=produced_units,
        cost=cost,
    )

    assert decision.from_stock == from_stock
    assert decision.to_stock == to_stock
    assert decision.produced_units == produced_units
    assert decision.cost == cost


@pytest.mark.parametrize(
    ("feature_name", "module_name"),
    [
        pytest.param(
            "Financial analysis",
            "smartbiz_ai.financial",
            id="financial-analysis",
        ),
        pytest.param(
            "Selling price recommendation",
            "smartbiz_ai.pricing",
            id="selling-price-recommendation",
        ),
        pytest.param(
            "Inventory management",
            "smartbiz_ai.inventory",
            id="inventory-management",
        ),
        pytest.param(
            "Stock forecasting",
            "smartbiz_ai.forecasting",
            id="stock-forecasting",
        ),
        pytest.param(
            "Low stock alert",
            "smartbiz_ai.alerts",
            id="low-stock-alert",
        ),
        pytest.param(
            "Restock recommendation",
            "smartbiz_ai.restock",
            id="restock-recommendation",
        ),
    ],
)
def test_smartbiz_requirements_not_implemented_yet(feature_name, module_name):
    """Mengonfirmasi fitur yang belum ada dalam repository dan tidak boleh dibuat secara palsu."""
    pytest.skip(
        f"Not currently testable because the required implementation does not exist: "
        f"{feature_name} ({module_name})."
    )


def test_product_scenarios_fixture_covers_multiple_umkm_cases(product_scenarios):
    """Fixture produk generik harus mencakup beberapa pola usaha yang berbeda."""
    assert len(product_scenarios) >= 5
    for product_name, product in product_scenarios.items():
        assert "start_stock" in product
        assert "demand" in product
        assert "options" in product
        assert product["start_stock"] >= 0
        assert product["demand"] > 0
        assert product["options"]
        assert all(isinstance(option, ProductionOption) for option in product["options"])

        graph = build_graph(
            int(product["start_stock"]),
            int(product["demand"]),
            list(product["options"]),
        )
        assert isinstance(graph, dict)


def test_bundled_dataset_produces_recommendations_for_all_products():
    data_dir = Path(__file__).resolve().parents[1] / "data" / "smartbiz_json"

    recommendations = recommend_all(data_dir)

    assert len(recommendations) == 30
    assert all(item["total_cost"] is not None for item in recommendations)
    assert sum(item["production_units"] > 0 for item in recommendations) == 22
    assert sum(item["total_cost"] for item in recommendations) == 7_667_500
