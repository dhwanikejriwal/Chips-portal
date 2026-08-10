"""Master Database Seeder for CHiPS Portal.

Runs all 4 database seeder scripts under seed_files/ sequentially:
  1. seed_login_districts_profiles.py (Districts, Statuses, Roles, Admin & DC/EDM accounts)
  2. seed_station_id_master.py        (Station ID counter series per district)
  3. seed_kit_tracker.py             (Master kit registrations, operators, station mappings)
  4. seed_pending_lists.py           (Pending L1/L2 hardware & onboarding queues)
"""
import sys
import os
import subprocess

def run_seeder(script_path: str, name: str):
    print(f"\n==================================================================")
    print(f"  RUNNING SEEDER: {name}")
    print(f"==================================================================")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    python_exe = sys.executable
    result = subprocess.run([python_exe, script_path], cwd=base_dir)
    if result.returncode != 0:
        print(f"Error running {name} (exit code {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"Completed: {name}\n")


def main():
    print("Starting Complete CHiPS Portal Database Seeding Pipeline...")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    seeders = [
        (os.path.join(base_dir, "seed_files", "seed_login_districts_profiles.py"), "1/4 Baseline Logins, Districts & Profiles Seeder"),
        (os.path.join(base_dir, "seed_files", "seed_station_id_master.py"), "2/4 Station ID Master Counters Seeder"),
        (os.path.join(base_dir, "seed_files", "seed_kit_tracker.py"), "3/4 Kit Tracker & Operators Seeder"),
        (os.path.join(base_dir, "seed_files", "seed_pending_lists.py"), "4/4 Pending Workflow Queues Seeder"),
    ]
    
    for script_path, name in seeders:
        if not os.path.exists(script_path):
            print(f"Error: Required seed file '{script_path}' not found!", file=sys.stderr)
            sys.exit(1)
        run_seeder(script_path, name)

    print("==================================================================")
    print("  ALL DATABASE SEEDERS COMPLETED SUCCESSFULLY!")
    print("==================================================================")

if __name__ == "__main__":
    main()
