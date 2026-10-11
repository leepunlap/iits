# Render-and-compare solver — prototype findings (negative result on the camera fit)

Attempted: fit a camera to an L1–L3 blueprint by rendering the model and comparing edge maps, then
rank competing part placements with it. Built and ran on `L1/201-bp01` step 1 (`build-01.jpg`).

## What was built

* `parts3d.js` — the kit's part geometry, shared by the viewer and the solver so both render identically.
* `blueprint_solve.html` — cuts the parts-list box off the blueprint, extracts **thin edges** (Sobel,
  not a luminance threshold: a blue beam otherwise becomes a solid blob), normalises both drawings by
  their ink bbox, then renders candidates as line drawings with hidden lines removed (white solids +
  black `EdgesGeometry`) and scores them. Exposes `__solve` and a `__debugImages` hook.
* `solve_blueprint.mjs` — driver: two-stage camera search (coarse grid, then refine), hypothesis
  ranking, and a forced-camera mode. Runs 672 cameras × 14 placements in ~4 s, ~7 s with refinement.

## What works

Edge extraction, normalisation, rendering and scoring all run, fast. The objective (symmetric chamfer
plus a sharp "unexplained edges at a 2 px tolerance" term) has real dynamic range — 0.55 to 0.75
across placements, i.e. 37% — so it is not flat.

## What fails

**The camera fit converges to a degenerate pose.** The best-scoring camera was `az 75, el 10` — nearly
edge-on. Rendering that pose beside the blueprint shows a flattened sliver against a proper 3/4 view.
It wins because a near-edge-on model has far fewer edges to penalise, so with nothing aligned the
cheapest thing to be is empty.

**Forcing a plausible camera is worse, not better.** At `az 45, el 40` the score degrades and **85% of
the blueprint's edge pixels are unexplained**; the ranking puts a plainly wrong placement first. So
`45/40` is not the true camera either — and I do not know what is.

**Consequence: the placements cannot be ranked.** In the searched-camera run "blue +1 hole" beat the
hand-built model by 7%, and I nearly reported that as the solver correcting my estimate. It is not
credible: it is two misaligned drawings being compared, and the sign of that margin would move if the
camera moved. **Retracted.**

## Root cause

1. **The objective has a degenerate minimum** — "fewer edges" scores well when nothing is aligned.
2. **Bbox normalisation destroys the pose signal** — it stretches any pose to fill the same box,
   so a flattened view is rescaled to match the target's footprint and the pose error is hidden.
3. **Chicken-and-egg** — fitting a camera needs a correct model; the model is my by-eye estimate, so
   no camera can align it well, and the bad alignment then corrupts the placement ranking.
4. **Unknown projection** — the blueprint's FOV/perspective is assumed (22°), and the elevation is
   only weekly constrained once the bbox has absorbed the scale.

## What would fix it

Break the chicken-and-egg by measuring the pose from **image features, not from the model**:

* **Hole ellipticity → elevation.** The kit's holes are circles; their apparent aspect ratio in the
  blueprint directly encodes the viewing elevation. That is a strong, model-free constraint.
* **Beam directions → azimuth.** Already measured and stable (45° / 125° across steps 3–6), so the
  azimuth is partly known before any model is rendered.
* **Stop bbox-normalising.** Keep a similarity fit but *penalise* aspect mismatch instead of absorbing
  it, so a wrong pose cannot be rescaled into looking right.
* **Verify visually at every step.** The debug hook exists for this; automated scores alone were
  actively misleading here — the first run scored every placement identically to 4 decimals because a
  stale `matrixWorld` rendered every part at the origin.

## Honest status

The pipeline is real and fast, but the premise is **not yet demonstrated**: on this blueprint the
comparison never aligned, so render-and-compare did not rank placements. A fixed camera angle across
steps remains a sound assumption (the edge-direction signature supports it) — but the angle still has
to be *found*, and that is where this prototype fails.
