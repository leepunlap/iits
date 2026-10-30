/* Assessment cubes — constant-velocity tumble, grabbable.
 *
 * NO DAMPING AND NO IDLE NUDGES, on purpose. Each cube is given one random angular
 * velocity at load and keeps it exactly until a person interferes: drag to turn it by hand,
 * release to flick it onto a new spin, tap to knock it. Anything that quietly changed the
 * motion on its own — drag toward rest, periodic random impulses — made the cubes look
 * restless and meant no two page loads behaved the same way twice. Constant velocity is
 * both calmer and more honest: what you see is what you set.
 */
(function () {
  'use strict';
  var stages = Array.prototype.slice.call(document.querySelectorAll('.cube-stage'));
  if (!stages.length) return;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function qmul(a, b) {
    return [a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3],
            a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2],
            a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1],
            a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0]];
  }
  function qnorm(q) { var m = Math.hypot(q[0],q[1],q[2],q[3]) || 1; return [q[0]/m,q[1]/m,q[2]/m,q[3]/m]; }
  function qaxis(ax, ay, az, ang) {           // quaternion from axis-angle
    var m = Math.hypot(ax, ay, az); if (m < 1e-9) return [1,0,0,0];
    var h = ang / 2, s = Math.sin(h) / m;
    return [Math.cos(h), ax*s, ay*s, az*s];
  }
  function qmat(q) {
    var w=q[0],x=q[1],y=q[2],z=q[3];
    return 'matrix3d(' + [1-2*(y*y+z*z), 2*(x*y+z*w), 2*(x*z-y*w), 0,
                          2*(x*y-z*w), 1-2*(x*x+z*z), 2*(y*z+x*w), 0,
                          2*(x*z+y*w), 2*(y*z-x*w), 1-2*(x*x+y*y), 0,
                          0,0,0,1].join(',') + ')';
  }
  var R = function (a, b) { return a + Math.random() * (b - a); };

  // Face centres in the cube's own space, matching the CSS transforms exactly:
  // .u is rotateX(90deg) translateZ, and rotateX(+90) sends +z to -y, so up is -y.
  var FACES = [['f',0,0,1],['b',0,0,-1],['r',1,0,0],['l',-1,0,0],['u',0,-1,0],['d',0,1,0]];

  var cubes = stages.map(function (stage) {
    var sp = R(0.30, 0.62);                  // one speed, kept forever unless touched
    var ax = R(-1,1), ay = R(-1,1), az = R(-1,1);
    var m = Math.hypot(ax,ay,az) || 1;
    return {
      stage: stage,
      el: stage.querySelector('.cube'),
      lbl: stage.querySelector('.lbl'),
      faces: FACES.map(function (f) {
        var el = stage.querySelector('.cube .' + f[0]);
        return el ? { el: el, n: [f[1], f[2], f[3]] } : null;
      }).filter(Boolean),
      q: qnorm([R(-1,1),R(-1,1),R(-1,1),R(-1,1)]),
      w: [ax/m*sp, ay/m*sp, az/m*sp],        // rad/s, constant
      drag: null
    };
  });

  // Which faces are nearer the viewer. Every face was drawn identically, so with six
  // translucent panes on screen at once nothing said which was front and which was back —
  // the cube read as a flat hexagon that occasionally seemed to turn inside out. The third
  // row of the rotation matrix gives each face centre's screen-space depth; CSS turns that
  // into opacity, border strength and highlight.
  function shade(c) {
    var q = c.q, w = q[0], x = q[1], y = q[2], z = q[3];
    var m02 = 2*(x*z - y*w), m12 = 2*(y*z + x*w), m22 = 1 - 2*(x*x + y*y);
    for (var i = 0; i < c.faces.length; i++) {
      var f = c.faces[i], n = f.n;
      var d = m02*n[0] + m12*n[1] + m22*n[2];      // -1 far .. +1 near
      f.el.style.setProperty('--d', ((d + 1) * 0.5).toFixed(3));
    }
  }

  function apply(c) {
    c.el.style.transform = qmat(c.q);
    shade(c);
    if (c.lbl) c.lbl.style.transform =
      qmat([c.q[0], -c.q[1], -c.q[2], -c.q[3]]) + ' translateZ(0px) scale(0.5)';
  }

  // Reduced motion slows the tumble to a crawl rather than freezing it. A small logo
  // turning once every couple of minutes is not the kind of motion the preference exists to
  // suppress, and a dead cube reads as broken. Interaction still works.
  if (reduce) cubes.forEach(function (c) { for (var k=0;k<3;k++) c.w[k] *= 0.12; });

  // --- grab, turn, release ------------------------------------------------------------
  var SENS = 0.011;                          // radians of turn per pixel dragged
  cubes.forEach(function (c) {
    c.stage.addEventListener('pointerdown', function (ev) {
      c.stage.setPointerCapture && c.stage.setPointerCapture(ev.pointerId);
      c.drag = { x: ev.clientX, y: ev.clientY, t: performance.now(), vx: 0, vy: 0, moved: 0,
                 prev: c.w.slice(), last: performance.now() };
      c.w = [0,0,0];                          // held still while under the finger
      ev.preventDefault();
    });

    c.stage.addEventListener('pointermove', function (ev) {
      var d = c.drag; if (!d) return;
      var dx = ev.clientX - d.x, dy = ev.clientY - d.y;
      var now = performance.now(), dt = Math.max(1, now - d.t) / 1000;
      // turn about the axis perpendicular to the drag, in SCREEN space, so the cube
      // follows the finger rather than its own local axes
      c.q = qnorm(qmul(qaxis(dy, dx, 0, Math.hypot(dx, dy) * SENS), c.q));
      d.vx = dx / dt; d.vy = dy / dt; d.moved += Math.hypot(dx, dy);
      d.x = ev.clientX; d.y = ev.clientY; d.t = now; d.last = now;
      apply(c);
    });

    function release(ev) {
      var d = c.drag; if (!d) return;
      c.drag = null;
      if (d.moved < 4) {                      // a tap, not a drag: knock it
        var r = c.stage.getBoundingClientRect();
        var ox = ((ev.clientX || r.left+r.width/2) - (r.left+r.width/2)) / (r.width/2);
        var oy = ((ev.clientY || r.top+r.height/2) - (r.top+r.height/2)) / (r.height/2);
        c.w = [oy*2.6 + R(-.3,.3), ox*2.6 + R(-.3,.3), (ox*oy)*1.8 + R(-.3,.3)];
      } else {                                // a flick: carry the throw into a new spin
        var s = SENS * 0.85;
        c.w = [d.vy * s, d.vx * s, 0];
      }
      var cap = 9;
      for (var k = 0; k < 3; k++) c.w[k] = Math.max(-cap, Math.min(cap, c.w[k]));
    }
    c.stage.addEventListener('pointerup', release);
    function cancel() { if (c.drag) { c.w = c.drag.prev; c.drag = null; } }
    c.stage.addEventListener('pointercancel', cancel);
    c.stage.addEventListener('lostpointercapture', function () { if (c.drag) release({}); });
    // a pointerup that lands anywhere else must still end the gesture; without this a mouse
    // released outside the tile leaves the cube held at zero velocity for good
    window.addEventListener('pointerup', function (ev) { if (c.drag) release(ev); });
    window.addEventListener('pointercancel', cancel);
    c.stage.addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' || ev.key === ' ') {
        c.w = [R(-2,2), R(-2,2), R(-1.2,1.2)]; ev.preventDefault();
      }
    });
  });

  var last = 0;
  function frame(t) {
    var dt = last ? Math.min((t - last)/1000, 0.05) : 0.016;
    last = t;
    for (var i = 0; i < cubes.length; i++) {
      var c = cubes[i];
      if (c.drag) {
        // a gesture with no events for a while is a lost pointer, not a held one
        if (t - c.drag.last > 1600) { c.w = c.drag.prev; c.drag = null; }
        else continue;
      }
      // PERPETUAL MOTION IS THE INVARIANT. Whatever went wrong upstream — a dropped
      // pointerup, a cancelled gesture, a flick that resolved to nothing — a cube that is
      // not in someone's hand must be turning. Re-seed rather than trusting the callers.
      if (Math.hypot(c.w[0], c.w[1], c.w[2]) < 0.02) {
        var ax = R(-1,1), ay = R(-1,1), az = R(-1,1), m = Math.hypot(ax,ay,az) || 1, sp0 = R(0.34, 0.64);
        c.w = [ax/m*sp0, ay/m*sp0, az/m*sp0];
      }
      var w = c.w, sp = Math.hypot(w[0], w[1], w[2]);
      if (sp > 1e-6) {
        c.q = qnorm(qmul(qaxis(w[0], w[1], w[2], sp * dt), c.q));
        apply(c);
      }
    }
    requestAnimationFrame(frame);
  }
  cubes.forEach(apply);
  requestAnimationFrame(frame);
})();
