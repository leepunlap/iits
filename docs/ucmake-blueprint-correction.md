docs: correct the step-1 3D claim - it does not match the blueprint

The blueprints/201-bp01-step1.json note and the earlier commit described the inferred
step-1 model as "~60%" against the photograph. That figure was an eyeball estimate and it
is wrong. Measured with the solver's own overlay metric (edge agreement at a 2 px
tolerance), across three camera angles:

  az 63  el 33.8   recall 8%   precision 24%
  az 111 el 33.8   recall 8%   precision 21%
  az 75  el 50     recall 6%   precision 23%

recall = share of the blueprint's edge pixels the render explains. At 6-8% the render does
not reproduce the drawing's geometry; the parts and the rough topology are recognisable,
the arrangement is not. The 3D model is therefore UNVALIDATED and must not be presented as
a reconstruction of step 1.

What is accurate, and how it was checked:
* the parts list for step 1 - 2x pin, 1x 7-hole beam (blue), 2x cross block, 2x 15-hole
  beam - matches the printed box (2x, 1x, 2x, 2x, 15孔) and an independent VLM reading
* the pose estimate - elevation 33.8 deg with a 0.2 deg interquartile spread over 56 hole
  ellipses - is deterministic geometry, not a judgement
* the harvest does find and segment the distinct parts, though its derived per-part
  features are meaningless for anything that is not a beam (the motor shows "holes=15"
  because vents read as enclosed regions). Those features are instrumentation for
  clustering, not measurements of the part.

The gate from here: a model ships only when its overlay recall is high, verified by
looking. This commit exists because I showed a render before it passed that gate.
