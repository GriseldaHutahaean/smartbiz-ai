"""Pengujian unit test untuk skrip pencarian UCS."""

import sys
from pathlib import Path
import pytest

# Menambahkan folder scripts ke dalam path pencarian Python
sys.path.append(str(Path(__file__).parent))

# pylint: disable=wrong-import-position
from ucs_production import (
    ProductionOption,
    Decision,
    build_graph,
    uniform_cost_search,
)


def test_build_graph_success():
    """Menguji pembuatan graf stok awal dan opsi produksi."""
    start_stock = 5
    demand = 20
    options = [
        ProductionOption(units=5, cost=25_000),
        ProductionOption(units=10, cost=50_000),
    ]

    graph = build_graph(start_stock, demand, options)

    assert 5 in graph
    assert len(graph[5]) == 2
    assert graph[5][0] == Decision(
        from_stock=5, to_stock=10, produced_units=5, cost=25_000
    )
    assert graph[5][1] == Decision(
        from_stock=5, to_stock=15, produced_units=10, cost=50_000
    )
    assert 20 not in graph


def test_uniform_cost_search_optimal_path():
    """Menguji UCS menemukan jalur biaya kumulatif g(n) minimal."""
    start_stock = 5
    demand = 20
    options = [
        ProductionOption(units=5, cost=25_000),
        ProductionOption(units=10, cost=50_000),
        ProductionOption(units=15, cost=75_000),
    ]

    graph = build_graph(start_stock, demand, options)
    result = uniform_cost_search(graph, start_stock, demand)

    assert result is not None
    path, total_cost = result

    assert total_cost == 75_000
    final_stock = path[-1].to_stock
    assert final_stock >= demand


def test_uniform_cost_search_chooses_cheaper_option():
    """Menguji UCS memilih opsi yang lebih murah untuk unit sama."""
    start_stock = 0
    demand = 10
    options = [
        ProductionOption(units=10, cost=60_000),
        ProductionOption(units=10, cost=40_000),
    ]

    graph = build_graph(start_stock, demand, options)
    result = uniform_cost_search(graph, start_stock, demand)

    assert result is not None
    path, total_cost = result

    assert total_cost == 40_000
    assert len(path) == 1
    assert path[0].cost == 40_000


def test_uniform_cost_search_already_at_goal():
    """Menguji kondisi stok awal sudah memenuhi target kebutuhan."""
    start_stock = 25
    demand = 20
    options = [ProductionOption(units=5, cost=25_000)]

    graph = build_graph(start_stock, demand, options)
    result = uniform_cost_search(graph, start_stock, demand)

    assert result is not None
    path, total_cost = result

    assert total_cost == 0
    assert not path


def test_uniform_cost_search_unreachable_goal():
    """Menguji jika tidak ada opsi produksi, sistem return None."""
    start_stock = 5
    demand = 20
    options = []

    graph = build_graph(start_stock, demand, options)
    result = uniform_cost_search(graph, start_stock, demand)

    assert result is None


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
def test_decision_stores_transition_and_cost(
    from_stock, to_stock, produced_units, cost
):
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
    ("start_stock", "demand", "options", "expected_graph"),
    [
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
            id="zero-unit-option-does-not-expand-forever",
        ),
    ],
)
def test_build_graph_scenarios(start_stock, demand, options, expected_graph):
    graph = build_graph(start_stock, demand, options)

    assert graph == expected_graph


@pytest.mark.parametrize(
    ("product", "start_stock", "demand", "options", "expected_cost"),
    [
        pytest.param(
            "Product A",
            5,
            20,
            [
                ProductionOption(5, 25_000),
                ProductionOption(10, 50_000),
                ProductionOption(15, 75_000),
            ],
            75_000,
            id="baseline-production-cost",
        ),
        pytest.param(
            "Product B",
            0,
            10,
            [ProductionOption(5, 4), ProductionOption(10, 5)],
            5,
            id="single-batch-beats-cheaper-small-batches",
        ),
        pytest.param(
            "Product C",
            0,
            10,
            [ProductionOption(3, 2), ProductionOption(8, 7)],
            8,
            id="multiple-paths-lowest-total-cost",
        ),
        pytest.param(
            "Product D",
            0,
            9,
            [ProductionOption(4, 0), ProductionOption(10, 1)],
            0,
            id="zero-cost-production",
        ),
    ],
)
def test_uniform_cost_search_returns_lowest_cumulative_cost(
    product, start_stock, demand, options, expected_cost
):
    graph = build_graph(start_stock, demand, options)

    result = uniform_cost_search(graph, start_stock, demand)

    assert result is not None, product
    path, total_cost = result
    assert total_cost == expected_cost
    assert total_cost == sum(decision.cost for decision in path)
    assert (path[-1].to_stock if path else start_stock) >= demand


@pytest.mark.parametrize(
    ("start_stock", "demand", "options", "expected_cost", "expected_steps"),
    [
        (10, 10, [ProductionOption(5, 20)], 0, 0),
        (12, 10, [], 0, 0),
        (0, 10, [], None, None),
    ],
)
def test_uniform_cost_search_goal_and_unreachable_edges(
    start_stock, demand, options, expected_cost, expected_steps
):
    graph = build_graph(start_stock, demand, options)

    result = uniform_cost_search(graph, start_stock, demand)

    if expected_cost is None:
        assert result is None
        return

    assert result is not None
    path, total_cost = result
    assert total_cost == expected_cost
    assert len(path) == expected_steps
