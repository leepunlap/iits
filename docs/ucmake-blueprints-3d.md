# 3D construction blueprints

The L1–L3 lessons show their build steps as **2D photographs** — L1 537, L2 717, L3 925, i.e. 2,179
JPEGs — and there is **no 3D geometry anywhere** in the ecosystem (the UCMake app bundle, the lessons
build tree and the deployed lessons all contain zero `.glb`/`.gltf`/`.obj`/`.ldr`/`.stl` files). So the
blueprints cannot simply be "rendered in 3D" from existing data: the models have to exist first.

What is now built is the **engine** they can be rendered with:

* `blueprint3d.html` — a three.js viewer (mirrored at `vendor/three/`, not a CDN) that draws bricks
  with studs, lights them, lets the student orbit/zoom/pan, and **steps through the assembly**
  (◀ ▶, a slider, 顯示全部, 自動旋轉).
* `blueprints/sample.json` — the model format, and a worked example.
* Verified in a real browser: model loads, WebGL context live, step 1 renders, stepping changes both
  the label and the image (headless screenshots 41 KB → 44 KB), no exceptions.

## Model format

One stud = 1 unit in x/z; one brick height = 1 unit in y.

```json
{
  "title": "示範模型：8×2 底盤 + 上層",
  "bricks": [ { "x":0, "y":0, "z":0, "w":8, "d":2, "h":1, "color":"#4b5563" } ],
  "steps":  [ { "label":"步驟 1：8×2 底盤", "bricks":[0] } ]
}
```

`bricks` are the pieces; `steps` list which bricks exist at each build step. A model needs authoring
once — the **step boundaries come free**, because each of the 2,179 photographs already documents one
step, so a finished model can be sliced into the same steps the lesson photos show.

## How to author them

1. **LDraw / Studio (recommended).** Free LEGO CAD; a modeler builds the model and exports `.ldr`.
   Every part is a simple text record (`1 <colour> <x y z> <matrix> <part.dat>`), and the kit uses a
   small set of standard brick parts — so a converter can map part ids onto the procedural brick
   geometry already in `blueprint3d.html` without shipping the LDraw parts library.
2. **Direct JSON** for simple models — the sample above is hand-authorable.
3. **From the photos** — not reliable; treat the photographs as the reference for a human modeler,
   not as a source of geometry.

## Scope, stated honestly

The engine is done; the **content is not**. 93 lessons (31 each in L1–L3) need their models modelled.
That is an authoring project, not a rendering task — roughly one model per lesson, each then sliced
into the steps the photos already define.
