"""Bounded source and fixture comparison with the pre-emitter-repair mean field."""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import types

import torch

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "forecast"))
import audit_fit_coverage as coverage
from wildfire.models import StructuredKernelModel
from wildfire.meanfield import propagate_mean_field

PRIOR = "99ce687b07f399bb09fd48e56759df75b9ba765e3ca88ccd74be11b81adadf74"
PRIOR_BURNOUT = "01c16f48df94ed521a32b15ce76db2e1b96c17e276a8071ffbfdd9fec6872447"


class WithoutExtraMetadata(ast.NodeTransformer):
    """Compare the unchanged no-callback path, not arbitrary extra callbacks."""
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return None
        return self.generic_visit(node)

    def visit_Assign(self, node):
        if any(isinstance(t, ast.Name) and t.id == "extra_source" for t in node.targets):
            return None
        return self.generic_visit(node)

    def visit_If(self, node):
        if any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "source_mode" for t in n.targets)
               for n in node.body):
            return None
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == "extra_source":
            node.id = "source"
        return node


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("Preserve the earlier compatibility evidence")
    blob = coverage._source_blob(REPO, "forecast/wildfire/meanfield.py", PRIOR)
    module = types.ModuleType("wildfire._pre_flaming_check")
    module.__package__ = "wildfire"
    sys.modules[module.__name__] = module
    exec(compile(blob, "frozen-1bd-meanfield.py", "exec"), module.__dict__)
    before = WithoutExtraMetadata().visit(deepcopy(coverage._function(blob, "propagate_mean_field")))
    after = WithoutExtraMetadata().visit(deepcopy(coverage._function(
        (REPO / "forecast/wildfire/meanfield.py").read_text(), "propagate_mean_field")))
    if ast.dump(before, include_attributes=False) != ast.dump(after, include_attributes=False):
        raise AssertionError("The normalized no-extra source path changed")
    burnout = coverage._source_blob(REPO, "forecast/wildfire/burnout.py", PRIOR_BURNOUT)
    if ast.dump(coverage._function(burnout, "source"), include_attributes=False) != ast.dump(
            coverage._function((REPO / "forecast/wildfire/burnout.py").read_text(), "source"), include_attributes=False):
        raise AssertionError("The local flaming-plus-smouldering source path changed")
    torch.set_num_threads(1)
    rows = []
    for frame in ("none", "wind", "d4"):
        for residence in (None, 6.):
            torch.manual_seed(3)
            old = StructuredKernelModel(3, 3, 2, 0., channel_names=["weather.wind_eastward_10m",
                "weather.wind_northward_10m", "weather.temperature_2m"], frame=frame, residence_hours=residence).eval()
            current = deepcopy(old)
            environment = torch.ones(1, 3, 7, 7)
            initial = torch.zeros(1, 1, 7, 7)
            initial[..., 3, 3] = 1
            options = dict(channel_names=old.channel_names, boundary="zero", initial_age_hours=torch.full_like(initial, 100.))
            a = module.propagate_mean_field(old, initial, environment, [1., 1.], burnout=old.flaming_window(), **options)
            b = propagate_mean_field(current, initial, environment, [1., 1.], burnout=current.flaming_window(), **options)
            if not torch.equal(a.valid, b.valid) or not torch.equal(a.new_burn_probability, b.new_burn_probability):
                raise AssertionError("A no-spotting fixture changed its masks or output")
            a.new_burn_probability.sum().backward()
            b.new_burn_probability.sum().backward()
            for (name, p), (other, q) in zip(old.named_parameters(), current.named_parameters()):
                if name != other or not ((p.grad is None and q.grad is None) or (p.grad is not None
                        and q.grad is not None and torch.equal(p.grad, q.grad))):
                    raise AssertionError("A no-spotting fixture changed a parameter gradient: " + name)
            rows.append(dict(frame=frame, residence_hours=residence, outputs_masks_all_parameter_gradients_bit_identical=True))
    record = dict(evidence_class="BOUNDED_SOURCE_AND_MECHANISM_CHECK_NOT_STUDY", prior_meanfield_sha256=PRIOR,
                  current_meanfield_sha256=coverage.sha(REPO / "forecast/wildfire/meanfield.py"),
                  non_extra_ast_identical_after_removing_only_new_metadata_branch=True,
                  local_burnout_source_ast_unchanged=True, controls=rows, script_sha256=coverage.sha(HERE),
                  limit="No spotting identity is asserted; four historical spotting phases require the flaming-only rerun.")
    coverage.write_new(args.out, record)
    print(json.dumps(dict(controls=len(rows), passed=True)))


if __name__ == "__main__":
    main()
