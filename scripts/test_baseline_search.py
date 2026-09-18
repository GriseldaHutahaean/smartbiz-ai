import pytest
from src.baseline_search import (
    ProductionOption,
    Decision,
    build_graph,
    uniform_cost_search,
)


def test_build_graph_success():
    """Menguji apakah graf dibangun dengan benar berdasarkan stok awal dan opsi produksi."""
    start_stock = 5
    demand = 20
    options = [
        ProductionOption(units=5, cost=25_000),
        ProductionOption(units=10, cost=50_000),
    ]

    graph = build_graph(start_stock, demand, options)

    # Memastikan state awal (5) tereksplorasi dan memiliki 2 cabang keputusan
    assert 5 in graph
    assert len(graph[5]) == 2

    # Memastikan detail transisi dari state 5
    assert graph[5][0] == Decision(
        from_stock=5, to_stock=10, produced_units=5, cost=25_000
    )
    assert graph[5][1] == Decision(
        from_stock=5, to_stock=15, produced_units=10, cost=50_000
    )

    # State >= 20 (goal) tidak boleh dikembangkan lagi
    assert 20 not in graph


def test_uniform_cost_search_optimal_path():
    """Menguji apakah UCS menemukan jalur dengan biaya kumulatif g(n) paling minimal."""
    start_stock = 5
    demand = 20
    options = [
        ProductionOption(units=5, cost=25_000),  # Rp5.000/unit
        ProductionOption(units=10, cost=50_000),  # Rp5.000/unit
        ProductionOption(units=15, cost=75_000),  # Rp5.000/unit
    ]

    graph = build_graph(start_stock, demand, options)
    result = uniform_cost_search(graph, start_stock, demand)

    assert result is not None
    path, total_cost = result

    # Total biaya minimum dari stok 5 ke 20 (butuh 15 unit) adalah Rp75.000
    assert total_cost == 75_000

    # Memastikan stok akhir mencapai atau melebihi goal (20)
    final_stock = path[-1].to_stock
    assert final_stock >= demand


def test_uniform_cost_search_chooses_cheaper_option():
    """Menguji bahwa UCS memilih opsi yang lebih murah meskipun jumlah unitnya sama."""
    start_stock = 0
    demand = 10

    # Opsi A lebih mahal daripada Opsi B
    options = [
        ProductionOption(units=10, cost=60_000),  # Opsi mahal
        ProductionOption(units=10, cost=40_000),  # Opsi murah
    ]

    graph = build_graph(start_stock, demand, options)
    result = uniform_cost_search(graph, start_stock, demand)

    assert result is not None
    path, total_cost = result

    # UCS harus memilih opsi dengan biaya Rp40.000
    assert total_cost == 40_000
    assert len(path) == 1
    assert path[0].cost == 40_000


def test_uniform_cost_search_already_at_goal():
    """Menguji kondisi ketika stok awal sudah memenuhi atau melebihi target kebutuhan."""
    start_stock = 25
    demand = 20
    options = [ProductionOption(units=5, cost=25_000)]

    graph = build_graph(start_stock, demand, options)
    result = uniform_cost_search(graph, start_stock, demand)

    assert result is not None
    path, total_cost = result

    # Jika stok awal >= goal, tidak perlu ada tindakan produksi (biaya = 0)
    assert total_cost == 0
    assert path == []


def test_uniform_cost_search_unreachable_goal():
    """Menguji jika tidak ada opsi produksi (graf kosong), sistem mengembalikan None."""
    start_stock = 5
    demand = 20
    options = []  # Tidak ada opsi produksi

    graph = build_graph(start_stock, demand, options)
    result = uniform_cost_search(graph, start_stock, demand)

    assert result is None
