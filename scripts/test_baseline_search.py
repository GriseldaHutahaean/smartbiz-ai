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
