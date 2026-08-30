/* Assessment cubes — rigid-body-ish tumble with quaternion state.
 *
 * Why a simulation instead of CSS keyframes: keyframes have no state. They cannot be
 * nudged, cannot carry momentum, and repeat exactly every cycle. Integrating an angular
 * velocity gives motion that can be struck and that never lands in the same orientation
 * twice, which is what actually reads as a physical object.
 *
 * The label is a plane at the cube's centre inside the same preserve-3d hierarchy, held
 * upright by applying the INVERSE rotation. That is what lets the near faces occlude it:
 * it is genuinely inside the box rather than drawn over it.
 */
(function () {
  'use strict';
  var stages = Array.prototype.slice.call(document.querySelectorAll('.cube-stage'));
  if (!stages.length) return;

  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // --- quaternion helpers (w,x,y,z) ---
  function qmul(a, b) {
    return [a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3],
            a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2],
            a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1],
            a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0]];
  }
  function qnorm(q) {
    var m = Math.hypot(q[0], q[1], q[2], q[3]) || 1;
    return [q[0]/m, q[1]/m, q[2]/m, q[3]/m];
  }
  function qmat(q) {                       // -> CSS matrix3d, column-major
    var w=q[0], x=q[1], y=q[2], z=q[3];
    var m = [1-2*(y*y+z*z), 2*(x*y+z*w),   2*(x*z-y*w),   0,
             2*(x*y-z*w),   1-2*(x*x+z*z), 2*(y*z+x*w),   0,
             2*(x*z+y*w),   2*(y*z-x*w),   1-2*(x*x+y*y), 0,
             0,0,0,1];
    return 'matrix3d(' + m.join(',') + ')';
  }

  var R = function (a, b) { return a + Math.random() * (b - a); };

  var cubes = stages.map(function (stage, i) {
    var el  = stage.querySelector('.cube');
    var lbl = stage.querySelector('.lbl');
    // every cube starts differently, so five of them never march in step
    var c = {
      stage: stage, el: el, lbl: lbl,
      q: qnorm([R(-1,1), R(-1,1), R(-1,1), R(-1,1)]),
      w: [R(-0.5,0.5), R(0.25,0.6) * (Math.random() < 0.5 ? -1 : 1), R(-0.35,0.35)],
      next: R(2.5, 7)                       // seconds until the next idle nudge
    };
    if (Math.random() < 0.5) c.w[1] = -c.w[1];
    return c;
  });

  // --- an impulse from a pointer: off-centre hits impart more spin, like a real strike ---
  function strike(c, ev) {
    var r = c.stage.getBoundingClientRect();
    var px = (ev.clientX !== undefined ? ev.clientX : r.left + r.width / 2);
    var py = (ev.clientY !== undefined ? ev.clientY : r.top + r.height / 2);
    var dx = (px - (r.left + r.width  / 2)) / (r.width  / 2);   // -1..1
    var dy = (py - (r.top  + r.height / 2)) / (r.height / 2);
    var lever = Math.min(1, Math.hypot(dx, dy)) * 0.75 + 0.35;
    // torque perpendicular to the offset: pushing the right edge spins it about Y, etc.
    c.w[0] += ( dy) * 5.2 * lever + R(-0.4, 0.4);
    c.w[1] += ( dx) * 5.2 * lever + R(-0.4, 0.4);
    c.w[2] += (dx * dy) * 3.0     + R(-0.5, 0.5);
    var cap = 13;
    for (var k = 0; k < 3; k++) c.w[k] = Math.max(-cap, Math.min(cap, c.w[k]));
  }

  cubes.forEach(function (c) {
    c.stage.addEventListener('pointerdown', function (ev) { strike(c, ev); }, { passive: true });
    c.stage.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ') { strike(c, {}); ev.preventDefault(); }
    });
  });

  function apply(c) {
    c.el.style.transform = qmat(c.q);
    // inverse rotation keeps the label facing the viewer; translateZ(0) keeps it at the
    // centre plane so the near faces sort in front of it
    // scale(.5) pairs with the 2x font-size in CSS: the glyphs rasterise at double
    // resolution and are scaled down here, which is what keeps them sharp through the matrix
    if (c.lbl) c.lbl.style.transform = qmat([c.q[0], -c.q[1], -c.q[2], -c.q[3]]) + ' translateZ(0px) scale(0.5)';
  }

  if (reduce) {
    cubes.forEach(function (c) { c.q = qnorm([0.92, -0.18, -0.32, -0.05]); apply(c); });
    return;
  }

  var last = 0;
  function frame(t) {
    var dt = last ? Math.min((t - last) / 1000, 0.05) : 0.016;   // clamp after a tab switch
    last = t;
    for (var i = 0; i < cubes.length; i++) {
      var c = cubes[i], w = c.w;
      var sp = Math.hypot(w[0], w[1], w[2]);
      if (sp > 1e-6) {                       // integrate: q <- dq * q
        var ang = sp * dt, h = ang / 2, sn = Math.sin(h) / sp;
        c.q = qnorm(qmul([Math.cos(h), w[0]*sn, w[1]*sn, w[2]*sn], c.q));
      }
      // drag pulls it back toward a lazy drift rather than to a dead stop
      var drag = Math.exp(-0.55 * dt);
      for (var k = 0; k < 3; k++) {
        w[k] *= drag;
        if (Math.abs(w[k]) < 0.18) w[k] += (Math.random() - 0.5) * 0.09 * dt * 60;
      }
      c.next -= dt;
      if (c.next <= 0) {                      // occasional idle nudge, so it never settles
        c.next = R(3, 9);
        w[0] += R(-0.5, 0.5); w[1] += R(-0.5, 0.5); w[2] += R(-0.35, 0.35);
      }
      apply(c);
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
