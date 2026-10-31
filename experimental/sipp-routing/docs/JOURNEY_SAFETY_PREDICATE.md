# Journey predicate and traceability

All uses of safe mean admissible under a specified mathematical model. A journey is a sequence of edge traversals or node waits, beginning at issue and ending with an admitted destination arrival followed by dwell. The executable abstract predicate emits the exact identifiers below.

| Identifier | Clause | Independent checker | Test |
|---|---|---|---|
| JS-1 | First leg begins at issue | frozen_checker._shape | test_predicate.test_each_requirement_is_detected |
| JS-2 | Legs are contiguous | frozen_checker._shape | same targeted-mutation test |
| JS-3 | Positive monotone durations, end by horizon | frozen_checker._shape | same targeted-mutation test |
| JS-4 | Exact declared edge duration | frozen_checker._shape | same targeted-mutation test |
| JS-5 | Edge continuity and incoming-edge turn rules | frozen_checker._shape | same targeted-mutation test |
| JS-6 | Waiting only at waitable nodes | frozen_checker._shape | same targeted-mutation test |
| JS-7 | Every node wait avoids member activity | frozen_checker._charge | same targeted-mutation test and union/subset metamorphic cases |
| JS-8 | Every edge traversal avoids member activity | frozen_checker._charge | same targeted-mutation test and legal-witness census |
| JS-9 | Peak within the member limit | frozen_checker.check_route | targeted mutation and test_full_checker.test_peak_contact_support_and_window_all_gate_the_journey |
| JS-10 | Incurred plus journey and requested dwell dose within budget | frozen_checker.check_route | targeted mutation and test_full_checker.test_complete_journey_dose_includes_history_and_dwell_once |
| JS-11 | Destination admission, opening and full dwell within horizon | frozen_checker._shape | targeted mutation and destination-window property cases |
| JS-12 | Issue contact and incurred budget admissible | frozen_checker._charge and check_route | targeted mutation test |

Every JS identifier is tested with an isolated mutation in experimental/sipp-routing/tests/test_predicate.py. The contact planner does not use peak/dose resource dominance. The abstract constant-flux predicate is a specification aid; actual centre flux is integrated by the copied complete-journey checker. Peak and dose under a different law require that law's complete enclosure argument.

Source support is an additional admission condition: unknown emitting sources cannot be declared cold. Export, bridge and decision tests retain unsupported states. A union contact-relaxation refusal does not certify a weighted k-of-m refusal; test_decision enforces this distinction.

The planner proposes a witness, the independent checker gates issuance, and unresolved is the recovery output. This is a certifying design pattern; it is not a claim of ASTM conformity or physical wildfire safety. Whole-road radiation and law v2 remain separate unresolved gates.
