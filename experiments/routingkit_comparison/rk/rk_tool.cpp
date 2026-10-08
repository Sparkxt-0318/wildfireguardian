// RoutingKit driver for the WildfireGuardian comparison experiments.
//
// Line protocol on stdin/stdout so Python can drive one long-lived process.
// Graphs are turn-expanded: expanded node i == directed road edge i, and an
// expanded arc (e1 -> e2) exists iff head(e1) == tail(e2) and the turn is not
// forbidden. Being "at" expanded node e means road edge e has been traversed.
// All times are integer milliseconds.
//
//   LOAD <slot> <graph.txt>                  build expanded graph + CH + CCH
//   BENCH <slot> <nqueries> <seed>           static speed benchmark -> JSON
//   BLOCK <slot> <k> e1 .. ek                block edges in the static metric
//   UNBLOCK_ALL <slot>                        restore base static metric
//   STATIC <slot> <src_node> <k> t1 .. tk    CCH query, multi-target
//   SETCLOSE <slot> <k> e1 c1 .. ek ck       per-edge closing time (ms)
//   CLEARCLOSE <slot>
//   TD <slot> <k> (src depart)xk <m> t1..tm  time-dependent deadline Dijkstra
//   TDTREE <slot> <k> (src depart)xk         earliest arrival at every node
//
// TD semantics: entering edge e at time t is allowed iff t + w(e) < close(e).
// With closures that never reopen this is FIFO, so Dijkstra is exact.
#include <routingkit/contraction_hierarchy.h>
#include <routingkit/customizable_contraction_hierarchy.h>
#include <routingkit/nested_dissection.h>
#include <routingkit/dijkstra.h>
#include <routingkit/inverse_vector.h>
#include <routingkit/timer.h>
#include <routingkit/sort.h>
#include <routingkit/permutation.h>

#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <vector>

using namespace RoutingKit;
using namespace std;

struct CSR {
	vector<unsigned> first_out, tail, head, weight;
};

static CSR make_csr(unsigned n, vector<unsigned> tail, vector<unsigned> head, vector<unsigned> weight) {
	auto p = compute_inverse_stable_sort_permutation_using_key(tail, n, [](unsigned x) { return x; });
	CSR g;
	g.tail = apply_inverse_permutation(p, tail);
	g.head = apply_inverse_permutation(p, head);
	g.weight = apply_inverse_permutation(p, weight);
	g.first_out = invert_vector(g.tail, n);
	return g;
}

struct Slot {
	unsigned N = 0, M = 0;
	vector<float> x, y;
	vector<unsigned> eu, ev, ew;
	vector<vector<unsigned>> out_edges, in_edges;
	// node-based graph
	CSR node_graph;
	// expanded graph
	CSR xg;
	vector<vector<unsigned>> arcs_into;  // expanded arcs whose head is edge e
	vector<unsigned> base_weight, cur_weight;
	unique_ptr<CustomizableContractionHierarchy> cch;
	unique_ptr<CustomizableContractionHierarchyMetric> metric;
	unique_ptr<CustomizableContractionHierarchyPartialCustomization> partial;
	vector<unsigned> blocked;
	vector<unsigned> close;  // per edge closing time
	double cch_order_ms = 0, cch_build_ms = 0, cch_customize_ms = 0;
};

static map<string, Slot> slots;
static const unsigned EDGE_FLAG = 1u << 31;

static unsigned parse_src(const string& tok) {
	return tok[0] == 'e' ? (EDGE_FLAG | (unsigned)stoul(tok.substr(1))) : (unsigned)stoul(tok);
}

static void load(const string& name, const string& file) {
	Slot& s = slots[name];
	s = Slot();
	ifstream in(file);
	unsigned T;
	in >> s.N >> s.M >> T;
	s.x.resize(s.N); s.y.resize(s.N);
	for (unsigned i = 0; i < s.N; ++i) { double a, b; in >> a >> b; s.x[i] = a; s.y[i] = b; }
	s.eu.resize(s.M); s.ev.resize(s.M); s.ew.resize(s.M);
	for (unsigned i = 0; i < s.M; ++i) in >> s.eu[i] >> s.ev[i] >> s.ew[i];
	set<pair<unsigned, unsigned>> forbidden;
	for (unsigned i = 0; i < T; ++i) { unsigned a, b; in >> a >> b; forbidden.insert({a, b}); }
	s.out_edges.assign(s.N, {}); s.in_edges.assign(s.N, {});
	for (unsigned e = 0; e < s.M; ++e) { s.out_edges[s.eu[e]].push_back(e); s.in_edges[s.ev[e]].push_back(e); }
	s.node_graph = make_csr(s.N, s.eu, s.ev, s.ew);
	vector<unsigned> t, h, w;
	for (unsigned e1 = 0; e1 < s.M; ++e1)
		for (unsigned e2 : s.out_edges[s.ev[e1]])
			if (!forbidden.count({e1, e2})) { t.push_back(e1); h.push_back(e2); w.push_back(s.ew[e2]); }
	s.xg = make_csr(s.M, t, h, w);
	s.arcs_into.assign(s.M, {});
	for (unsigned a = 0; a < s.xg.head.size(); ++a) s.arcs_into[s.xg.head[a]].push_back(a);
	s.base_weight = s.xg.weight;
	s.cur_weight = s.base_weight;
	vector<float> mx(s.M), my(s.M);
	for (unsigned e = 0; e < s.M; ++e) { mx[e] = (s.x[s.eu[e]] + s.x[s.ev[e]]) / 2; my[e] = (s.y[s.eu[e]] + s.y[s.ev[e]]) / 2; }
	long long t0 = get_micro_time();
	auto order = compute_nested_node_dissection_order_using_inertial_flow(s.M, s.xg.tail, s.xg.head, my, mx);
	long long t1 = get_micro_time();
	s.cch.reset(new CustomizableContractionHierarchy(order, s.xg.tail, s.xg.head));
	long long t2 = get_micro_time();
	s.metric.reset(new CustomizableContractionHierarchyMetric(*s.cch, s.cur_weight));
	s.metric->customize();
	long long t3 = get_micro_time();
	s.partial.reset(new CustomizableContractionHierarchyPartialCustomization(*s.cch));
	s.close.assign(s.M, inf_weight);
	s.cch_order_ms = (t1 - t0) / 1000.0; s.cch_build_ms = (t2 - t1) / 1000.0; s.cch_customize_ms = (t3 - t2) / 1000.0;
	cout << "{\"ok\":true,\"nodes\":" << s.N << ",\"edges\":" << s.M << ",\"turn_arcs\":" << s.xg.head.size()
	     << ",\"forbidden\":" << T << ",\"cch_order_ms\":" << s.cch_order_ms << ",\"cch_build_ms\":" << s.cch_build_ms
	     << ",\"cch_customize_ms\":" << s.cch_customize_ms << "}" << endl;
}

// ---------------------------------------------------------------- static
static void print_path(const vector<unsigned>& p) {
	cout << "[";
	for (unsigned i = 0; i < p.size(); ++i) cout << (i ? "," : "") << p[i];
	cout << "]";
}

static void static_query(Slot& s, unsigned src, const vector<unsigned>& targets) {
	CustomizableContractionHierarchyQuery q(*s.metric);
	long long t0 = get_micro_time();
	bool any_src = false, any_tgt = false;
	if (src & EDGE_FLAG) { q.add_source(src & ~EDGE_FLAG, 0); any_src = true; }
	else for (unsigned e : s.out_edges[src])
		if (find(s.blocked.begin(), s.blocked.end(), e) == s.blocked.end()) { q.add_source(e, s.ew[e]); any_src = true; }
	for (unsigned d : targets) for (unsigned e : s.in_edges[d]) { q.add_target(e, 0); any_tgt = true; }
	unsigned dist = inf_weight; vector<unsigned> path;
	if (any_src && any_tgt) { q.run(); dist = q.get_distance(); if (dist != inf_weight) path = q.get_node_path(); }
	long long t1 = get_micro_time();
	cout << "{\"dist\":" << (dist == inf_weight ? -1 : (long long)dist) << ",\"us\":" << (t1 - t0) << ",\"path\":";
	print_path(path);
	cout << "}" << endl;
}

static void block(Slot& s, const vector<unsigned>& edges, double* us_out = nullptr) {
	long long t0 = get_micro_time();
	s.partial->reset();
	for (unsigned e : edges) {
		s.blocked.push_back(e);
		for (unsigned a : s.arcs_into[e]) { s.cur_weight[a] = inf_weight; s.partial->update_arc(a); }
	}
	s.partial->customize(*s.metric);
	long long t1 = get_micro_time();
	if (us_out) *us_out = t1 - t0;
}

static void unblock_all(Slot& s) {
	s.partial->reset();
	for (unsigned e : s.blocked)
		for (unsigned a : s.arcs_into[e]) { s.cur_weight[a] = s.base_weight[a]; s.partial->update_arc(a); }
	s.blocked.clear();
	s.partial->customize(*s.metric);
}

// ---------------------------------------------------------------- time dependent
struct TDResult { vector<unsigned> arrival; Dijkstra* d; };

static Dijkstra& td_run(Slot& s, const vector<pair<unsigned, unsigned>>& sources, const vector<unsigned>* targets,
                        unsigned& best_edge, unsigned& best_time) {
	static map<Slot*, Dijkstra> dij;
	Dijkstra& d = dij[&s];
	d.reset(s.xg.first_out, s.xg.tail, s.xg.head);
	// Dijkstra::add_source overwrites; keep best per source edge.
	map<unsigned, unsigned> seed;
	for (auto& sd : sources) {
		if (sd.first & EDGE_FLAG) {
			unsigned e = sd.first & ~EDGE_FLAG;
			auto it = seed.find(e); if (it == seed.end() || sd.second < it->second) seed[e] = sd.second;
			continue;
		}
		for (unsigned e : s.out_edges[sd.first]) {
			unsigned arr = sd.second + s.ew[e];
			if (arr < s.close[e]) { auto it = seed.find(e); if (it == seed.end() || arr < it->second) seed[e] = arr; }
		}
	}
	for (auto& kv : seed) d.add_source(kv.first, kv.second);
	vector<char> is_target;
	if (targets) { is_target.assign(s.M, 0); for (unsigned t : *targets) for (unsigned e : s.in_edges[t]) is_target[e] = 1; }
	best_edge = invalid_id; best_time = inf_weight;
	auto get_weight = [&](unsigned arc, unsigned t) -> unsigned {
		unsigned e = s.xg.head[arc];
		unsigned w = s.ew[e];
		return (t + w < s.close[e]) ? w : inf_weight;
	};
	while (!d.is_finished()) {
		auto r = d.settle(get_weight);
		if (targets && is_target[r.node]) { best_edge = r.node; best_time = r.distance; break; }
	}
	return d;
}

static void td_query(Slot& s, const vector<pair<unsigned, unsigned>>& sources, const vector<unsigned>& targets) {
	long long t0 = get_micro_time();
	unsigned be, bt;
	Dijkstra& d = td_run(s, sources, &targets, be, bt);
	vector<unsigned> path;
	if (be != invalid_id) path = d.get_node_path_to(be);
	long long t1 = get_micro_time();
	// which source node was used: tail of first edge
	long long used = path.empty() ? -1 : (long long)s.eu[path[0]];  // tail of first edge
	cout << "{\"arrival\":" << (be == invalid_id ? -1 : (long long)bt) << ",\"us\":" << (t1 - t0)
	     << ",\"source\":" << used << ",\"path\":";
	print_path(path);
	cout << "}" << endl;
}

static void td_tree(Slot& s, const vector<pair<unsigned, unsigned>>& sources) {
	long long t0 = get_micro_time();
	unsigned be, bt;
	Dijkstra& d = td_run(s, sources, nullptr, be, bt);
	vector<long long> arr(s.N, -1);
	for (auto& sd : sources) if (!(sd.first & EDGE_FLAG)) arr[sd.first] = sd.second;
	for (unsigned e = 0; e < s.M; ++e) {
		unsigned a = d.get_distance_to(e);
		if (a != inf_weight) { long long& v = arr[s.ev[e]]; if (v < 0 || a < v) v = a; }
	}
	long long t1 = get_micro_time();
	cout << "{\"us\":" << (t1 - t0) << ",\"arrival\":[";
	for (unsigned i = 0; i < s.N; ++i) cout << (i ? "," : "") << arr[i];
	cout << "]}" << endl;
}

// ---------------------------------------------------------------- benchmark
static void bench(Slot& s, unsigned nq, unsigned seed) {
	mt19937 rng(seed);
	vector<pair<unsigned, unsigned>> qs;
	while (qs.size() < nq) {
		unsigned a = rng() % s.N, b = rng() % s.N;
		if (a != b && !s.out_edges[a].empty() && !s.in_edges[b].empty()) qs.push_back({a, b});
	}
	auto stats = [](vector<double> v) {
		sort(v.begin(), v.end());
		ostringstream o;
		double sum = 0; for (double x : v) sum += x;
		o << "{\"mean_us\":" << sum / v.size() << ",\"median_us\":" << v[v.size() / 2] << ",\"p95_us\":" << v[v.size() * 95 / 100] << "}";
		return o.str();
	};
	ostringstream out;
	out << "{";
	// node-based (ignores turn restrictions) Dijkstra + CH
	{
		Dijkstra d(s.node_graph.first_out, s.node_graph.tail, s.node_graph.head);
		vector<double> tt; vector<unsigned> dd;
		for (auto& q : qs) {
			long long t0 = get_micro_time();
			d.reset().add_source(q.first);
			while (!d.is_finished()) { if (d.settle(ScalarGetWeight(s.node_graph.weight)).node == q.second) break; }
			tt.push_back(get_micro_time() - t0); dd.push_back(d.get_distance_to(q.second));
		}
		out << "\"node_dijkstra\":" << stats(tt) << ",";
		long long t0 = get_micro_time();
		auto ch = ContractionHierarchy::build(s.N, s.node_graph.tail, s.node_graph.head, s.node_graph.weight);
		long long t1 = get_micro_time();
		ContractionHierarchyQuery cq(ch);
		vector<double> ct; unsigned mismatch = 0;
		for (unsigned i = 0; i < qs.size(); ++i) {
			long long a = get_micro_time();
			unsigned dist = cq.reset().add_source(qs[i].first).add_target(qs[i].second).run().get_distance();
			ct.push_back(get_micro_time() - a);
			if (dist != dd[i]) ++mismatch;
		}
		out << "\"node_ch_build_ms\":" << (t1 - t0) / 1000.0 << ",\"node_ch_query\":" << stats(ct) << ",\"node_ch_mismatch\":" << mismatch << ",";
	}
	// expanded (turn-aware)
	{
		Dijkstra d(s.xg.first_out, s.xg.tail, s.xg.head);
		vector<double> tt; vector<unsigned> dd;
		for (auto& q : qs) {
			vector<char> tgt(s.M, 0); for (unsigned e : s.in_edges[q.second]) tgt[e] = 1;
			long long t0 = get_micro_time();
			d.reset(); for (unsigned e : s.out_edges[q.first]) d.add_source(e, s.ew[e]);
			unsigned best = inf_weight;
			while (!d.is_finished()) { auto r = d.settle(ScalarGetWeight(s.base_weight)); if (tgt[r.node]) { best = r.distance; break; } }
			tt.push_back(get_micro_time() - t0); dd.push_back(best);
		}
		out << "\"turn_dijkstra\":" << stats(tt) << ",";
		long long t0 = get_micro_time();
		auto ch = ContractionHierarchy::build(s.M, s.xg.tail, s.xg.head, s.base_weight);
		long long t1 = get_micro_time();
		ContractionHierarchyQuery cq(ch);
		vector<double> ct; unsigned mismatch = 0;
		for (unsigned i = 0; i < qs.size(); ++i) {
			long long a = get_micro_time();
			cq.reset();
			for (unsigned e : s.out_edges[qs[i].first]) cq.add_source(e, s.ew[e]);
			for (unsigned e : s.in_edges[qs[i].second]) cq.add_target(e, 0);
			unsigned dist = cq.run().get_distance();
			ct.push_back(get_micro_time() - a);
			if (dist != dd[i]) ++mismatch;
		}
		out << "\"turn_ch_build_ms\":" << (t1 - t0) / 1000.0 << ",\"turn_ch_query\":" << stats(ct) << ",\"turn_ch_mismatch\":" << mismatch << ",";
		unblock_all(s);
		CustomizableContractionHierarchyQuery q(*s.metric);
		vector<double> qt; mismatch = 0;
		for (unsigned i = 0; i < qs.size(); ++i) {
			long long a = get_micro_time();
			q.reset();
			for (unsigned e : s.out_edges[qs[i].first]) q.add_source(e, s.ew[e]);
			for (unsigned e : s.in_edges[qs[i].second]) q.add_target(e, 0);
			unsigned dist = q.run().get_distance();
			qt.push_back(get_micro_time() - a);
			if (dist != dd[i]) ++mismatch;
		}
		out << "\"turn_cch_order_ms\":" << s.cch_order_ms << ",\"turn_cch_build_ms\":" << s.cch_build_ms
		    << ",\"turn_cch_customize_ms\":" << s.cch_customize_ms << ",\"turn_cch_query\":" << stats(qt) << ",\"turn_cch_mismatch\":" << mismatch << ",";
		// full re-customization timing
		long long a = get_micro_time(); s.metric->customize(); long long b = get_micro_time();
		out << "\"turn_cch_full_recustomize_ms\":" << (b - a) / 1000.0 << ",";
		// partial customization: block k random edges (a "fire update"), then restore
		out << "\"partial_customize\":[";
		unsigned ks[] = {10, 100, 1000};
		for (unsigned i = 0; i < 3; ++i) {
			vector<unsigned> es; for (unsigned j = 0; j < ks[i]; ++j) es.push_back(rng() % s.M);
			double us; block(s, es, &us);
			unblock_all(s);
			out << (i ? "," : "") << "{\"blocked_edges\":" << ks[i] << ",\"ms\":" << us / 1000.0 << "}";
		}
		out << "],";
		// time dependent deadline Dijkstra with random closing times
		for (unsigned e = 0; e < s.M; ++e) s.close[e] = (rng() % 5 == 0) ? (rng() % 1800000) : inf_weight;
		vector<double> tdt;
		for (auto& q : qs) {
			long long a2 = get_micro_time();
			unsigned be, bt; vector<unsigned> tg{q.second};
			td_run(s, {{q.first, 0}}, &tg, be, bt);
			tdt.push_back(get_micro_time() - a2);
		}
		s.close.assign(s.M, inf_weight);
		out << "\"turn_td_deadline_dijkstra\":" << stats(tdt);
	}
	out << "}";
	cout << out.str() << endl;
}

int main() {
	ios::sync_with_stdio(false);
	string line;
	while (getline(cin, line)) {
		istringstream in(line);
		string cmd, name; in >> cmd;
		if (cmd.empty()) continue;
		if (cmd == "QUIT") break;
		in >> name;
		if (cmd == "LOAD") { string f; in >> f; load(name, f); continue; }
		Slot& s = slots.at(name);
		if (cmd == "BENCH") { unsigned n, seed; in >> n >> seed; bench(s, n, seed); }
		else if (cmd == "BLOCK") { unsigned k; in >> k; vector<unsigned> es(k); for (auto& e : es) in >> e; double us; block(s, es, &us); cout << "{\"us\":" << us << "}" << endl; }
		else if (cmd == "UNBLOCK_ALL") { unblock_all(s); cout << "{}" << endl; }
		else if (cmd == "STATIC") { string tok; unsigned k; in >> tok >> k; unsigned src = parse_src(tok); vector<unsigned> t(k); for (auto& x : t) in >> x; static_query(s, src, t); }
		else if (cmd == "SETCLOSE") { unsigned k; in >> k; for (unsigned i = 0; i < k; ++i) { unsigned e, c; in >> e >> c; s.close[e] = c; } cout << "{}" << endl; }
		else if (cmd == "CLEARCLOSE") { s.close.assign(s.M, inf_weight); cout << "{}" << endl; }
		else if (cmd == "TD" || cmd == "TDTREE") {
			unsigned k; in >> k; vector<pair<unsigned, unsigned>> src(k);
			for (auto& p : src) { string tok; in >> tok >> p.second; p.first = parse_src(tok); }
			if (cmd == "TD") { unsigned m; in >> m; vector<unsigned> t(m); for (auto& x : t) in >> x; td_query(s, src, t); }
			else td_tree(s, src);
		} else cout << "{\"error\":\"unknown\"}" << endl;
		cout.flush();
	}
}
