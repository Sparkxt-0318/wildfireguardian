"""Virtual vehicle unit in the FDS C064 grass fire (DESIGN.md step 8).

Everything this package produces is SIMULATED: the "sensor readings" are computed from FDS 6.11.1 model fields of
the CSIRO C064 case (1 m cells), not measured. FDS is a model, so agreement with it is not validation.

Modules:
  fields     FDS volume frames, trilinear sampling, ROI + 5 s composite, truth front metrics (kcf_heat.voxel)
  lwir       TC001 virtual camera: ray-marched 8-14 um band radiance -> apparent temperature
  radar_path 60 GHz two-way excess phase through the hot-gas refractivity field; synthetic frames for the
             crossing.radar_flame detector; soot / plasma attenuation estimates
  plate      copper flux-plate energy balance driven by a flux history, inverted with crossing.flux.FluxEstimator
  pipeline   runs the laptop modules (thermal, geometry, depth, heat) on the virtual readings
  run        command line entry point (python -m virtual_fds.run)
"""
