"""Module solver.py: CSP Constraint Solver & Decision Engine untuk SmartBiz AI.

Membaca dataset JSON (smartbiz_json) dan menyelesaikan Constraint Satisfaction
Problem (CSP) menggunakan propagasi AC-3 dan Backtracking dengan heuristik MRV.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class UnsatisfiableConstraintError(Exception):
    """Custom exception ketika tidak ada solusi yang memenuhi batasan."""
    pass


# ============================================================================
# 1. DATASET LOADER (Integrasi smartbiz_json)
# ============================================================================

class DatasetLoader:
    """Memuat dan mengonsolidasi seluruh file JSON dari folder dataset."""

    def __init__(self, data_dir: str = "smartbiz_json"):
        self.data_path = Path(data_dir)

    def _load_json(self, filename: str) -> List[Dict[str, Any]]:
        file_file = self.data_path / filename
        if not file_file.exists():
            logging.warning(f"File {filename} tidak ditemukan di {self.data_path}")
            return []
        with open(file_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_all_data(self) -> Dict[str, Any]:
        """Membaca seluruh entitas JSON yang diperlukan untuk optimasi."""
        return {
            "categories": self._load_json("categories.json"),
            "products": self._load_json("products.json"),
            "ingredients": self._load_json("ingredients.json"),
            "product_recipes": self._load_json("product_recipes.json"),
            "production_options": self._load_json("production_options.json"),
            "expenses": self._load_json("expenses.json"),
            "sales_analytics": self._load_json("sales_analytics.json"),
        }


# ============================================================================
# 2. ABSTRAKSI TERSTRUKTUR CSP ENGINE
# ============================================================================

@dataclass(frozen=True)
class Variable:
    """Variabel keputusan CSP."""
    name: str
    category: str  # 'production' atau 'restock'


@dataclass
class Constraint:
    """Batasan operasional antar variabel."""
    scope: List[Variable]
    condition: Callable[..., bool]
    description: str = ""

    def is_satisfied(self, assignment: Dict[Variable, Any]) -> bool:
        if not all(v in assignment for v in self.scope):
            return True
        args = [assignment[v] for v in self.scope]
        return self.condition(*args)


class CSPSolver:
    """Mesin pemecah CSP dengan AC-3 dan Backtracking MRV."""

    def __init__(
        self,
        variables: List[Variable],
        domains: Dict[Variable, List[Any]],
        constraints: List[Constraint],
        max_backtracks: int = 10000,
    ):
        self.variables = variables
        self.domains = {v: list(domains[v]) for v in variables}
        self.constraints = constraints
        self.max_backtracks = max_backtracks
        self.backtrack_count = 0

        self.binary_constraints: List[Tuple[Variable, Variable, Constraint]] = []
        for c in constraints:
            if len(c.scope) == 2:
                v1, v2 = c.scope[0], c.scope[1]
                self.binary_constraints.append((v1, v2, c))
                self.binary_constraints.append((v2, v1, c))

    def ac3(self) -> bool:
        """Propagasi Arc Consistency 3 (AC-3) untuk pemangkasan domain."""
        queue = list(self.binary_constraints)
        while queue:
            xi, xj, constraint = queue.pop(0)
            if self._revise(xi, xj, constraint):
                if not self.domains[xi]:
                    return False
                for neighbor_i, neighbor_j, c in self.binary_constraints:
                    if neighbor_j == xi and neighbor_i != xj:
                        queue.append((neighbor_i, neighbor_j, c))
        return True

    def _revise(self, xi: Variable, xj: Variable, constraint: Constraint) -> bool:
        revised = False
        to_remove = []
        for x in self.domains[xi]:
            has_support = any(
                constraint.is_satisfied({xi: x, xj: y}) for y in self.domains[xj]
            )
            if not has_support:
                to_remove.append(x)
                revised = True
        for val in to_remove:
            self.domains[xi].remove(val)
        return revised

    def select_unassigned_variable(self, assignment: Dict[Variable, Any]) -> Variable:
        """Pilihan variabel berdasarkan MRV (Minimum Remaining Values)."""
        unassigned = [v for v in self.variables if v not in assignment]
        return min(unassigned, key=lambda var: len(self.domains[var]))

    def solve(self) -> Dict[Variable, Any]:
        """Eksekusi pencarian solusi CSP."""
        for v in self.variables:
            if not self.domains.get(v):
                raise UnsatisfiableConstraintError(
                    f"Domain variabel '{v.name}' kosong (Unsatisfiable)."
                )

        if not self.ac3():
            raise UnsatisfiableConstraintError(
                "Inkonsistensi terdeteksi: AC-3 memangkas domain hingga kosong."
            )

        self.backtrack_count = 0
        solution = self._backtrack({})
        if solution is None:
            raise UnsatisfiableConstraintError(
                "Tidak ada kombinasi keputusan yang memenuhi seluruh Hard Constraints."
            )
        return solution

    def _backtrack(self, assignment: Dict[Variable, Any]) -> Optional[Dict[Variable, Any]]:
        if len(assignment) == len(self.variables):
            return assignment

        self.backtrack_count += 1
        if self.backtrack_count > self.max_backtracks:
            return None

        var = self.select_unassigned_variable(assignment)
        for value in self.domains[var]:
            assignment[var] = value
            if self._is_consistent(var, assignment):
                result = self._backtrack(assignment)
                if result is not None:
                    return result
            del assignment[var]
        return None

    def _is_consistent(self, var: Variable, assignment: Dict[Variable, Any]) -> bool:
        for c in self.constraints:
            if var in c.scope and not c.is_satisfied(assignment):
                return False
        return True


# ============================================================================
# 3. DOMAIN OPTIMIZER (Menerjemahkan Dataset ke CSP)
# ============================================================================

class SmartBizOptimizer:
    """Wrapper yang memetakan data dari smartbiz_json ke struktur CSP Solver."""

    def __init__(self, data_dir: str = "smartbiz_json", budget_limit: float = 500000.0):
        self.loader = DatasetLoader(data_dir)
        self.raw_data = self.loader.load_all_data()
        self.budget_limit = budget_limit

    def build_and_solve(self) -> Dict[str, Any]:
        """Membangun variabel, domain, dan batasan dari dataset JSON lalu mengeksekusi solver."""
        products = self.raw_data.get("products", [])
        ingredients = self.raw_data.get("ingredients", [])
        recipes = self.raw_data.get("product_recipes", [])
        options = self.raw_data.get("production_options", [])

        if not products:
            raise UnsatisfiableConstraintError("Dataset produk kosong.")

        # Opsi batch produksi dari production_options.json
        batch_choices = [
            opt.get("batch_size", 0) for opt in options
        ] if options else [0, 5, 10, 15, 20]

        variables: List[Variable] = []
        domains: Dict[Variable, List[Any]] = {}

        # 1. Variabel Produksi per Produk
        prod_vars: Dict[int, Variable] = {}
        for p in products:
            p_id = p.get("id", p.get("product_id"))
            var = Variable(name=f"prod_p{p_id}", category="production")
            variables.append(var)
            prod_vars[p_id] = var
            domains[var] = list(batch_choices)

        # 2. Variabel Restock per Bahan Baku
        restock_vars: Dict[int, Variable] = {}
        for ing in ingredients:
            ing_id = ing.get("id", ing.get("ingredient_id"))
            var = Variable(name=f"restock_i{ing_id}", category="restock")
            variables.append(var)
            restock_vars[ing_id] = var
            domains[var] = [0, 5, 10, 15, 20, 25, 30]

        constraints: List[Constraint] = []

        # Constraint 1: Batasan Anggaran Kas (Budget Limit)
        # Biaya total (Biaya Produksi + Biaya Restock Bahan Baku) <= Budget
        ing_cost_map = {
            ing.get("id", ing.get("ingredient_id")): float(ing.get("cost_per_unit", ing.get("unit_cost", 1000)))
            for ing in ingredients
        }
        prod_cost_map = {
            p.get("id", p.get("product_id")): float(p.get("production_cost", p.get("cost", 5000)))
            for p in products
        }

        def budget_constraint(*args) -> bool:
            # Half args are prod, half are restock
            n_prod = len(prod_vars)
            prod_vals = args[:n_prod]
            restock_vals = args[n_prod:]

            total_prod_cost = sum(
                p_val * prod_cost_map.get(p_id, 5000)
                for p_val, p_id in zip(prod_vals, prod_vars.keys())
            )
            total_restock_cost = sum(
                r_val * ing_cost_map.get(ing_id, 1000)
                for r_val, ing_id in zip(restock_vals, restock_vars.keys())
            )
            return (total_prod_cost + total_restock_cost) <= self.budget_limit

        all_scope = list(prod_vars.values()) + list(restock_vars.values())
        constraints.append(
            Constraint(
                scope=all_scope,
                condition=budget_constraint,
                description="Hard Constraint: Daily Budget Limit",
            )
        )

        # Constraint 2: Batasan Kebutuhan Resep (Recipe Material Balance)
        # Stok awal + Restock >= Konsumsi untuk Produksi
        for ing in ingredients:
            ing_id = ing.get("id", ing.get("ingredient_id"))
            current_stock = float(ing.get("current_stock", ing.get("stock", 0)))
            r_var = restock_vars[ing_id]

            # Cari resep produk yang menggunakan bahan baku ini
            related_p_ids = [
                r.get("product_id") for r in recipes if r.get("ingredient_id") == ing_id
            ]
            related_p_vars = [prod_vars[pid] for pid in related_p_ids if pid in prod_vars]

            if related_p_vars:
                def recipe_constraint(r_val, *p_vals, i_id=ing_id, c_stock=current_stock) -> bool:
                    needed = 0.0
                    for p_val, pid in zip(p_vals, related_p_ids):
                        # Ambil kuantitas resep per unit
                        recipe_item = next(
                            (rec for rec in recipes if rec.get("product_id") == pid and rec.get("ingredient_id") == i_id),
                            None,
                        )
                        qty = float(recipe_item.get("quantity", 1.0)) if recipe_item else 1.0
                        needed += p_val * qty
                    return (c_stock + r_val) >= needed

                constraints.append(
                    Constraint(
                        scope=[r_var] + related_p_vars,
                        condition=recipe_constraint,
                        description=f"Hard Constraint: Recipe Balance for Ingredient {ing_id}",
                    )
                )

        solver = CSPSolver(variables, domains, constraints)
        raw_solution = solver.solve()

        # Format output hasil rekomendasi
        formatted_result = {"production": {}, "restock": {}}
        for var, val in raw_solution.items():
            if var.category == "production":
                p_id = int(var.name.replace("prod_p", ""))
                formatted_result["production"][p_id] = val
            elif var.category == "restock":
                ing_id = int(var.name.replace("restock_i", ""))
                formatted_result["restock"][ing_id] = val

        return formatted_result