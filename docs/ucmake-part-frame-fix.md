lab-device: fix the part frames - every beam was floating 0.9 above the ground

Measured the built geometry instead of guessing it, and the numbers exposed a systematic
bug:

  beam        y 0.90..1.80   z -2.00..-1.00     <- floating, and offset in z
  crossblock  y 0.00..0.90   z  0.00.. 2.65     <- on the ground
  pin         y -0.33..0.33  z -0.33..0.33

beamMesh rotated the profile and then translated by (0, h, -2r), which lifted every beam a
full part-height above y=0 and shifted its footprint two units along z. A model made only of
beams looked fine because the error was uniform; the moment a beam met an L-mount or a pin,
the parts could not seat. That is why the mounts never reached the blue beam no matter how
the placement was tuned - it was never a placement problem.

Fixed by translating (0, 0, 2r) so every part shares one frame: footprint at the origin on
the hole pitch, sitting on y=0. Verified by measurement:

  beam        y 0.00..0.90   z 0.00..1.00
  crossblock  y 0.00..0.90   z 0.00..2.65

Also in this change:
* the L-mount is now ONE integral extruded L-profile with a shared corner hole. Built as two
  separate boxes its arms did not meet and its four pins floated free of the part.
* step 1 re-placed on the corrected frames: two parallel 15-hole beams, two L-mounts bridging
  both of them at one end, the blue 7-hole beam perpendicular on top, two pins in holes 2 and
  4 of the near beam.

Method note: measure the geometry, do not reason about it. This bug survived a dozen renders
because nothing ever printed the bounding boxes.
