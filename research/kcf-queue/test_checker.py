import copy, hashlib, json, os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checker

HERE = os.path.dirname(os.path.abspath(__file__))


def base_data():
    return {"cell_close": {},
            "nodes": {"0": {"cell": 0}, "1": {"cell": 1}, "2": {"cell": 2}},
            "edges": {"0": {"tail": 0, "head": 1, "D": 60, "cap_vph": 100, "segs": [[5, "1/7"]]},
                      "1": {"tail": 1, "head": 2, "D": 60, "cap_vph": 100, "segs": [[6, "0/1"]]}},
            "forbidden": [], "shelters": [1, 2]}


def make(paths=((("0", 0),), (("0", 60),)), close=None, start=0, spread=0, binding=None, mut=None, N=None, **top):
    """Hand-built certificate: owner A (subject), vehicles k with given paths. rho .85, cap 100 => n_e = 1."""
    data = base_data()
    if close:
        data["cell_close"] = close
    if mut:
        mut(data)
    cert = {"schema": "kcf-queue.cert/1", "H": 3600, "dwell": 120, "bin_s": 60, "rho": 0.85, "data": data,
            "owners": [{"id": "A", "origin": 0, "N": N or len(paths), "start": start, "spread": spread,
                        "role": "subject"}],
            "vehicles": [{"owner": "A", "k": k, "path": [list(x) for x in p]} for k, p in enumerate(paths)],
            "claim": {"subject": "A", "all_cleared": True,
                      "binding": binding or {"kind": "shelter", "id": 1, "vehicle": ["A", 1], "slack": 3360}}}
    cert.update(top)
    rehash(cert)
    return cert


def rehash(cert):
    cert["input_sha256"] = hashlib.sha256(
        json.dumps(cert["data"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def B(kind, i, k, slack):
    return {"kind": kind, "id": i, "vehicle": ["A", k], "slack": slack}


def codes(cert):
    return {f["code"] for f in checker.check(cert)["failures"]}


class T(unittest.TestCase):
    def ok(self, cert):
        r = checker.check(cert)
        self.assertTrue(r["valid"], r["failures"])
        return r

    def bad(self, cert, expect):
        self.assertEqual(codes(cert), set(expect), checker.check(cert)["failures"])

    # --- valid ---
    def test_valid_queue(self):
        # k1 waits at the origin for the next bin; arrivals 60, 120; slacks 3420, 3360 -> binding k1
        r = self.ok(make())
        self.assertEqual(r["binding"], B("shelter", "1", 1, 3360))

    def test_valid_release_curve(self):
        # r_0 = 10+floor(100*1/4)=35, r_1 = 10+floor(100*3/4)=85
        c = make(paths=((("0", 35),), (("0", 85),)), start=10, spread=100, binding=B("shelter", "1", 1, 3335))
        self.ok(c)

    def test_valid_capacity_floor(self):
        # cap 200: floor(85*200/6000)=2 so two entries in one bin are fine; tie -> k0
        c = make(paths=((("0", 0),), (("0", 0),)), binding=B("shelter", "1", 0, 3420),
                 mut=lambda d: d["edges"]["0"].update(cap_vph=200))
        self.ok(c)

    def test_valid_edge_binding(self):
        # closure 100 on cell 5, D=60, z=1/7: ceil(100-60/7)=ceil(91.43)=92 ; k1 enters 60: slack 91-60=31
        c = make(close={"5": 100}, binding=B("edge", "0", 1, 31))
        self.ok(c)
        self.assertEqual(checker.check(c)["binding"]["slack"], 31)

    def test_valid_node_binding(self):
        # origin cell 0 closes at 70; k1 waits and enters at 60 < 70: slack 69-60=9
        self.ok(make(close={"0": 70}, binding=B("node", "0", 1, 9)))

    def test_valid_pass_through_closed_node(self):
        # node 1 closes at 10 but nobody waits there; paths end at node 2 (shelter, cell 2 open)
        c = make(paths=((("0", 0), ("1", 60)), (("0", 60), ("1", 120))), close={"1": 10},
                 binding=B("shelter", "2", 1, 3300))
        c["claim"]["binding"]["id"] = 2
        self.ok(c)

    def test_valid_shelter_boundary(self):
        # arrival 3420+60=3480 = H-dwell allowed, slack 0
        self.ok(make(paths=((("0", 0),), (("0", 3420),)), binding=B("shelter", "1", 1, 0)))

    # --- invalid, one per code ---
    def test_hash(self):
        c = make()
        c["input_sha256"] = "0" * 64
        self.bad(c, {"HASH"})

    def test_schema_dzero(self):
        self.bad(make(mut=lambda d: d["edges"]["0"].update(D=0)), {"SCHEMA"})

    def test_schema_entry_over_H(self):
        self.assertIn("SCHEMA", codes(make(paths=((("0", 0),), (("0", 3601),)))))

    def test_schema_two_subjects(self):
        c = make()
        c["owners"].append({"id": "B", "origin": 0, "N": 1, "start": 0, "spread": 0, "role": "subject"})
        self.assertIn("SCHEMA", codes(c))

    def test_schema_garbage_never_raises(self):
        for x in (None, 5, "x", [], {}, {"schema": "kcf-queue.cert/1"}, {"data": 3}):
            r = checker.check(x)
            self.assertFalse(r["valid"])
            self.assertIn("SCHEMA", {f["code"] for f in r["failures"]} | {"SCHEMA"})
        c = make()
        c["vehicles"][0]["path"] = [[None, "a"]]
        self.assertIn("SCHEMA", codes(c))

    def test_count_missing_vehicle(self):
        c = make(binding=B("shelter", "1", 0, 3420))
        del c["vehicles"][1]
        c["owners"][0]["N"] = 2
        self.bad(c, {"COUNT"})

    def test_count_duplicate_k(self):
        c = make(binding=B("shelter", "1", 0, 3420))
        c["vehicles"][1]["k"] = 0
        c["vehicles"][1]["path"] = [["0", 60]]
        self.assertIn("COUNT", codes(c))

    def test_release_curve_declared(self):
        c = make()
        c["vehicles"][0]["release"] = 5  # extension field, spec formula gives 0
        self.bad(c, {"RELEASE_CURVE"})

    def test_route_before_release(self):
        # r_1 = 10+floor(100*3/4)=85, entry at 84 is too early; k1 slack 3480-144=3336
        c = make(paths=((("0", 35),), (("0", 84),)), start=10, spread=100, binding=B("shelter", "1", 1, 3336))
        self.bad(c, {"ROUTE"})

    def test_route_wrong_origin(self):
        c = make()
        c["owners"][0]["origin"] = 1
        self.bad(c, {"ROUTE"})

    def test_route_forbidden(self):
        c = make(paths=((("0", 0), ("1", 60)), (("0", 60),)), binding=B("shelter", "1", 1, 3360),
                 mut=lambda d: d.update(forbidden=[["0", "1"]]))
        # k0 arrives at 2 at 120, k1 at 1 at 120: slack tie 3360, id "1" < "2" -> k1
        self.bad(c, {"ROUTE"})

    def test_route_discontinuous(self):
        c = make(paths=((("0", 0), ("0", 60)), (("0", 60),)), binding=B("shelter", "1", 1, 3360))
        self.assertIn("ROUTE", codes(c))

    def test_route_too_early_second_entry(self):
        # edge 1 entered at 59 < 0+60; k0 arrives 119 (slack 3361), k1 slack 3360 -> k1
        c = make(paths=((("0", 0), ("1", 59)), (("0", 60),)))
        self.bad(c, {"ROUTE"})

    def test_route_empty_and_unknown_edge(self):
        self.assertIn("ROUTE", codes(make(paths=((), (("0", 60),)))))
        self.assertIn("ROUTE", codes(make(paths=((("9", 0),), (("0", 60),)))))

    def test_edge_closed(self):
        # lo=92; k1 enters at 92 -> closed. slack 91-92=-1
        self.bad(make(close={"5": 100}, paths=((("0", 0),), (("0", 92),)), binding=B("edge", "0", 1, -1)),
                 {"EDGE_CLOSED"})

    def test_wait_after_closure(self):
        # origin closes at 70, k1 waits until 70 -> WAIT, node slack 69-70=-1
        self.bad(make(close={"0": 70}, paths=((("0", 0),), (("0", 70),)), binding=B("node", "0", 1, -1)), {"WAIT"})

    def test_wait_at_origin_without_waiting(self):
        # origin closes at 0: even k0 (t == a == 0) fails; k1 waited: slack -1-60=-61
        r = checker.check(make(close={"0": 0}, binding=B("node", "0", 1, -61)))
        self.assertEqual([(f["code"], f["k"]) for f in r["failures"]], [("WAIT", 0), ("WAIT", 1)])

    def test_wait_mid_path(self):
        # node 1 closes at 10; k1 reaches it at 120 and waits until 130: WAIT, slack 9-130=-121
        c = make(paths=((("0", 0), ("1", 60)), (("0", 60), ("1", 130))), close={"1": 10},
                 binding=B("node", "1", 1, -121))
        self.bad(c, {"WAIT"})

    def test_capacity(self):
        # both enter edge 0 in bin 0, n_e=1; tie slack 3420 -> k0
        self.bad(make(paths=((("0", 0),), (("0", 0),)), binding=B("shelter", "1", 0, 3420)), {"CAPACITY"})

    def test_capacity_counts_neighbours(self):
        c = make()
        c["owners"].append({"id": "B", "origin": 0, "N": 1, "start": 0, "spread": 0, "role": "neighbour"})
        c["vehicles"].append({"owner": "B", "k": 0, "path": [["0", 0]]})
        self.bad(c, {"CAPACITY"})

    def test_shelter_not_a_shelter(self):
        c = make(mut=lambda d: d.update(shelters=[2]))
        self.assertIn("SHELTER", codes(c))

    def test_shelter_too_late(self):
        # arrival 3481 > 3480, slack -1
        self.bad(make(paths=((("0", 0),), (("0", 3421),)), binding=B("shelter", "1", 1, -1)), {"SHELTER"})

    def test_shelter_closed(self):
        # shelter cell 1 closes at 200: need a < 80. k0 arrives 60 ok (slack 19), k1 arrives 120 (slack -41)
        self.bad(make(close={"1": 200}, binding=B("shelter", "1", 1, -41)), {"SHELTER"})

    def test_binding_mismatch(self):
        self.bad(make(binding=B("shelter", "1", 0, 3420)), {"BINDING_MISMATCH"})
        self.bad(make(binding=B("shelter", "1", 1, 3359)), {"BINDING_MISMATCH"})

    def test_failure_cap(self):
        c = make(paths=tuple(() for _ in range(60)))
        r = checker.check(c)
        self.assertEqual(len(r["failures"]), 50)

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            g, b = os.path.join(d, "g.json"), os.path.join(d, "b.json")
            with open(g, "w") as f: json.dump(make(), f)
            with open(b, "w") as f: json.dump(make(binding=B("shelter", "1", 0, 1)), f)
            run = lambda *a: subprocess.run([sys.executable, os.path.join(HERE, "checker.py"), *a],
                                            capture_output=True, text=True)
            self.assertEqual(run(g).returncode, 0)
            r = run(g, b)
            self.assertEqual(r.returncode, 1)
            self.assertIn("BINDING_MISMATCH", r.stdout)


if __name__ == "__main__":
    unittest.main()
