"""PENUMBRA: passive multistatic RF sensing mesh for urban counter-UAS.

Sub-packages
------------
physics   bistatic geometry, radar equation, RCS scaling, rotor micro-Doppler, diffraction
sim       urban scene, target kinematics, synthetic IQ / range-Doppler generation
dsp       cross-ambiguity function, direct-signal cancellation, CFAR, spectrograms
ml        multimodal graph-temporal detector + calibration
tracking  multistatic UKF tracker and the canonical track schema
reasoning evidence ledger that explains each track decision
c2        Cursor-on-Target and SAPIENT-style adapters
edge      node runtime pipeline
"""
__version__ = "0.1.0"
