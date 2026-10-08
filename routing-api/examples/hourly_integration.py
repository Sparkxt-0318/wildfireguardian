"""Use a full extracted hourly release with its pinned environment."""
import argparse
from wildfireguardian_routing import ReleaseRuntime

p = argparse.ArgumentParser()
p.add_argument("release_directory")
p.add_argument("output_directory", help="Must not already exist")
p.add_argument("--research", action="store_true", help="Explicitly accept declared research construction")
p.add_argument("--native", action="store_true", help="Rerun original forecast inference")
a = p.parse_args()
report = ReleaseRuntime(a.release_directory).run_hourly(
    a.output_directory, mode="research" if a.research else "strict", native=a.native,
    save_hazard=True)
for row in report["rows"]:
    print(row["result"]["status"], row["proof_level"])
print("Entire backend process seconds:", report["api_process_wall_s"])
