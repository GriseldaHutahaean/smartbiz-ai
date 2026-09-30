from solver import SmartBizOptimizer, UnsatisfiableConstraintError

def run_app():
    print("==================================================")
    print("      SMARTBIZ AI - DECISION SUPPORT ENGINE       ")
    print("==================================================")

    # Inisialisasi Optimizer dengan folder 'smartbiz_json'
    # Anggaran kas dialokasikan Rp500.000
    optimizer = SmartBizOptimizer(data_dir="smartbiz_json", budget_limit=500000.0)

    try:
        recommendations = optimizer.build_and_solve()
        
        print("\n[+] REKOMENDASI BATCH PRODUKSI (Unit):")
        for prod_id, qty in recommendations["production"].items():
            print(f"    - Product ID {prod_id}: {qty} unit")

        print("\n[+] REKOMENDASI RESTOCK BAHAN BAKU (Unit/Kg):")
        for ing_id, qty in recommendations["restock"].items():
            print(f"    - Ingredient ID {ing_id}: {qty} unit")

        print("\n==================================================")
        print(" Status: Rekomendasi Legal & Optimal (CSP Approved)")
        print("==================================================")

    except UnsatisfiableConstraintError as err:
        print(f"\n[!] PERINGATAN KEPUTUSAN: {err}")

if __name__ == "__main__":
    run_app()