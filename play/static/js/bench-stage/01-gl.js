/* The herbalism bench's stage, part 1: the renderer.
 *
 * A small hand-written WebGL1 renderer, for the reason 00-math.js gives: the app ships no
 * third-party JavaScript. It does two things, lit meshes and soft points, and nothing else.
 *
 * THE LIGHT IS THE HOUSE LIGHT, carried into a real renderer. dice3d.js and scene3d.js
 * both light every face with one ambient term, one diffuse term and one tight specular
 * term against a light that belongs to the ROOM, never to the object, because a light
 * baked onto faces "spins with those faces" (reported from the table, twice). The same
 * three terms run here per pixel, against lights that stand in the world while the tool
 * drops, squashes and turns beneath them:
 *   - an ambient term, the sky or the room;
 *   - a cool directional fill: the day, the dusk or the moon, by the scene clock;
 *   - a warm point key: the camp fire, or the lamp when there is a roof;
 *   - two more warm points that only the tool switches on: its own fire or embers, and
 *     the ember flare of a hit.
 * Brass keeps the house's tight highlight (an exponent near 26 and up); wood, clay and
 * stone get broad, weak ones, so the eye reads the material from the sheen.
 *
 * NO TEXTURES ARE LOADED. Wood grain, stone speckle, clay mottling and the lumpy-to-glossy
 * base of the Mix game are value noise evaluated on the object's own coordinates, so a
 * pattern stays stuck to the thing it belongs to as it moves. The only image is the
 * procedural ground (03-ground.js), painted into an array and uploaded.
 *
 * CONTEXT LOSS. Khronos' "HandlingContextLost" page is the recipe: preventDefault on
 * `webglcontextlost`, then on `webglcontextrestored` recreate every program, buffer and
 * texture. So no GPU handle lives on a mesh or a texture record: they live in maps on the
 * renderer keyed by id, and a restore simply empties the maps. Every mesh keeps its arrays
 * on the CPU, and the next draw uploads it again.
 */
(function () {
  "use strict";
  var K = window.BenchStageKit = window.BenchStageKit || {};
  var M = K.math;

  var LIT_VS = [
    "attribute vec3 aPos;",
    "attribute vec3 aNrm;",
    "attribute vec2 aUv;",
    "uniform mat4 uModel;",
    "uniform mat4 uViewProj;",
    "uniform mat3 uNrmMat;",
    "varying vec3 vW;",
    "varying vec3 vN;",
    "varying vec2 vUv;",
    "varying vec3 vObj;",
    "void main() {",
    "  vec4 w = uModel * vec4(aPos, 1.0);",
    "  vW = w.xyz;",
    "  vN = uNrmMat * aNrm;",
    "  vUv = aUv;",
    "  vObj = aPos;",
    "  gl_Position = uViewProj * w;",
    "}"
  ].join("\n");

  var LIT_FS = [
    "#ifdef GL_FRAGMENT_PRECISION_HIGH",
    "precision highp float;",
    "#else",
    "precision mediump float;",
    "#endif",
    "varying vec3 vW;",
    "varying vec3 vN;",
    "varying vec2 vUv;",
    "varying vec3 vObj;",
    "uniform vec3 uColor;",
    "uniform float uAlpha;",
    "uniform float uSpec;",
    "uniform float uShin;",
    "uniform float uMetal;",
    "uniform vec3 uEmit;",
    "uniform float uPattern;",
    "uniform float uPatScale;",
    "uniform float uBump;",
    "uniform float uFresnel;",
    "uniform float uUseTex;",
    "uniform sampler2D uTex;",
    "uniform vec2 uUvScale;",
    "uniform float uUnlit;",
    "uniform float uRadial;",
    "uniform float uGround;",
    "uniform float uGlint;",
    "uniform vec3 uEye;",
    "uniform vec3 uAmb;",
    "uniform vec3 uKeyPos;",
    "uniform vec3 uKeyCol;",
    "uniform vec3 uFillDir;",
    "uniform vec3 uFillCol;",
    "uniform vec3 uGlowPos;",
    "uniform vec3 uGlowCol;",
    "uniform vec3 uFlarePos;",
    "uniform vec3 uFlareCol;",
    "uniform float uExposure;",
    "uniform float uReveal;",
    "uniform vec3 uBg;",
    "uniform vec2 uRes;",
    "uniform vec2 uFade;",
    "float hash(vec3 p) {",
    "  p = fract(p * 0.3183099 + vec3(0.11, 0.17, 0.13));",
    "  p *= 17.0;",
    "  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));",
    "}",
    "float vnoise(vec3 x) {",
    "  vec3 i = floor(x);",
    "  vec3 f = fract(x);",
    "  f = f * f * (3.0 - 2.0 * f);",
    "  return mix(mix(mix(hash(i), hash(i + vec3(1.0, 0.0, 0.0)), f.x),",
    "                 mix(hash(i + vec3(0.0, 1.0, 0.0)), hash(i + vec3(1.0, 1.0, 0.0)), f.x), f.y),",
    "             mix(mix(hash(i + vec3(0.0, 0.0, 1.0)), hash(i + vec3(1.0, 0.0, 1.0)), f.x),",
    "                 mix(hash(i + vec3(0.0, 1.0, 1.0)), hash(i + vec3(1.0, 1.0, 1.0)), f.x), f.y), f.z);",
    "}",
    "vec3 point(vec3 pos, vec3 col, float range, vec3 N, vec3 V, vec3 base, vec3 specCol, float k) {",
    "  vec3 L = pos - vW;",
    "  float d = length(L);",
    "  L /= max(d, 0.0001);",
    "  float att = 1.0 / (1.0 + d * d * range);",
    "  float diff = max(dot(N, L), 0.0);",
    "  float sp = pow(max(dot(N, normalize(L + V)), 0.0), uShin) * k * smoothstep(0.0, 0.15, diff);",
    "  return col * att * (base * diff + specCol * sp);",
    "}",
    "void main() {",
    "  vec3 base = uColor;",
    "  float gloss = 1.0;",
    "  if (uUseTex > 0.5) {",
    "    vec4 t = texture2D(uTex, vUv * uUvScale);",
    "    base *= t.rgb;",
    "    gloss = t.a;",
    "  }",
    "  vec3 N = normalize(vN);",
    "  vec3 V = normalize(uEye - vW);",
    // Face the viewer, whatever the winding: an open vessel's inner wall and a leaf seen
    // from below are both lit from the side the eye is on. Hidden faces are depth-tested.
    "  if (dot(N, V) < 0.0) N = -N;",
    "  float s = uPatScale;",
    "  if (uPattern > 0.5 && uPattern < 1.5) {",
    "    float g = vnoise(vObj * 2.5 * s);",
    "    float st = vnoise(vec3(vObj.x * 1.4, vObj.y * 24.0, vObj.z * 24.0) * s + g * 2.2);",
    "    base *= 0.74 + 0.38 * st;",
    "  } else if (uPattern > 1.5 && uPattern < 2.5) {",
    // Stone: a broad mottle, a fine grain, and faint dark and pale flecks. The first pass
    // stepped hard flecks at one scale and read as sprinkles on a cake, not as granite.
    "    float n = vnoise(vObj * 7.0 * s) * 0.55 + vnoise(vObj * 23.0 * s) * 0.3 + vnoise(vObj * 61.0 * s) * 0.15;",
    "    base *= 0.8 + 0.32 * n;",
    "    base *= 1.0 - 0.16 * smoothstep(0.72, 0.9, vnoise(vObj * 140.0 * s));",
    "    base *= 1.0 + 0.1 * smoothstep(0.75, 0.92, vnoise(vObj * 170.0 * s + 3.7));",
    "  } else if (uPattern > 2.5 && uPattern < 3.5) {",
    "    base *= 0.86 + 0.24 * vnoise(vObj * 7.0 * s);",
    "    base *= 1.0 + 0.18 * step(0.9, vnoise(vObj * 60.0 * s));",
    "  } else if (uPattern > 3.5 && uPattern < 4.5) {",
    // The Mix base: lumps are a bent normal, so gloss rising is the bumps calming down.
    "    vec3 q = vObj * 11.0 * s;",
    "    float n0 = vnoise(q);",
    "    vec3 gr = vec3(vnoise(q + vec3(0.07, 0.0, 0.0)) - n0, vnoise(q + vec3(0.0, 0.07, 0.0)) - n0,",
    "                   vnoise(q + vec3(0.0, 0.0, 0.07)) - n0) / 0.07;",
    "    N = normalize(N - uBump * gr * 0.35);",
    "    base *= 0.9 + 0.16 * n0 * uBump;",
    "  } else if (uPattern > 4.5 && uPattern < 5.5) {",
    "    float n = vnoise(vObj * 16.0 * s);",
    "    base *= 0.8 + 0.4 * n;",
    "    gloss *= 0.6 + 0.8 * vnoise(vObj * 5.0 * s);",
    "  } else if (uPattern > 5.5 && uPattern < 6.5) {",
    "    base *= 0.82 + 0.3 * vnoise(vObj * 26.0 * s);",
    "  } else if (uPattern > 6.5) {",
    // Ash and char: three octaves, because one octave of value noise at this scale showed
    // its lattice as soft squares, like a low-resolution photograph.
    "    float n = vnoise(vObj * 17.0 * s) * 0.5 + vnoise(vObj * 43.0 * s) * 0.3 + vnoise(vObj * 107.0 * s) * 0.2;",
    "    base *= 0.68 + 0.5 * n;",
    "  }",
    "  float a = uAlpha;",
    "  if (uRadial > 0.0) a *= pow(clamp(1.0 - length(vUv), 0.0, 1.0), uRadial);",
    "  vec3 col;",
    "  if (uUnlit > 0.5) {",
    "    col = base + uEmit;",
    "  } else {",
    "    vec3 specCol = mix(vec3(1.0), base * 1.6, uMetal);",
    "    float k = uSpec * gloss + uGlint;",
    "    col = base * uAmb;",
    "    float fd = max(dot(N, uFillDir), 0.0);",
    "    float fs = pow(max(dot(N, normalize(uFillDir + V)), 0.0), uShin) * k * smoothstep(0.0, 0.15, fd);",
    "    col += uFillCol * (base * fd + specCol * fs);",
    "    col += point(uKeyPos, uKeyCol, 0.11, N, V, base, specCol, k);",
    "    col += point(uGlowPos, uGlowCol, 1.2, N, V, base, specCol, k);",
    "    col += point(uFlarePos, uFlareCol, 2.0, N, V, base, specCol, k);",
    "    col += uEmit;",
    "  }",
    "  if (uFresnel > 0.0) {",
    "    float f = pow(1.0 - max(dot(N, V), 0.0), 3.0);",
    "    a = clamp(a + uFresnel * f, 0.0, 1.0);",
    "    col += vec3(0.95, 0.82, 0.6) * f * uFresnel * 0.45;",
    "  }",
    "  col *= uExposure;",
    "  if (uGround > 0.5) {",
    // The ground fades into --bg twice over: by distance, so the horizon never shows an
    // edge, and through a screen vignette, so every aspect from narrow to 21:9 ends in the
    // page's own dark rather than in a hard rectangle.
    "    float vis = 1.0 - smoothstep(uFade.x, uFade.y, length(vW.xz));",
    "    vec2 q = (gl_FragCoord.xy / uRes - 0.5) * 2.0;",
    "    vis *= 1.0 - smoothstep(0.55, 1.18, length(q * vec2(0.9, 1.0)));",
    "    col = mix(uBg, col, vis);",
    "  }",
    "  col = mix(uBg, col, uReveal);",
    "  gl_FragColor = vec4(col, a);",
    "}"
  ].join("\n");

  /* A point sprite has ONE depth for its whole square. Tested at its centre, a puff of
     steam over a pan was cut off along a straight line wherever the liquid below was
     nearer the eye than the puff's middle (seen in the harness as hard-edged rectangles
     of steam). So the depth is taken at the puff's FRONT: the point is pulled toward the
     camera by its own size before it is projected, and its screen size is kept from the
     unshifted position. */
  var PT_VS = [
    "attribute vec3 aPos;",
    "attribute vec4 aCol;",
    "attribute float aSize;",
    "uniform mat4 uView;",
    "uniform mat4 uProj;",
    "uniform float uPx;",
    "uniform float uMaxPt;",
    "varying vec4 vCol;",
    "void main() {",
    "  vec4 v = uView * vec4(aPos, 1.0);",
    "  float w = max(-v.z, 0.001);",
    "  v.z += aSize * 1.2;",
    "  gl_Position = uProj * v;",
    "  gl_PointSize = clamp(aSize * uPx / w, 1.0, uMaxPt);",
    "  vCol = aCol;",
    "}"
  ].join("\n");

  var PT_FS = [
    "precision mediump float;",
    "varying vec4 vCol;",
    "uniform float uExposure;",
    "uniform float uReveal;",
    "void main() {",
    "  float r = length(gl_PointCoord - 0.5) * 2.0;",
    "  float a = 1.0 - smoothstep(0.3, 1.0, r);",
    "  if (a <= 0.0) discard;",
    "  gl_FragColor = vec4(vCol.rgb * uExposure, vCol.a * a * uReveal);",
    "}"
  ].join("\n");

  /* Probe once, and let the probe go: a page can hold only a handful of live contexts
     (Chromium starts dropping the oldest at sixteen), and a probe that kept its context
     would spend one for nothing. */
  var probed = null;
  function supported() {
    if (probed !== null) return probed;
    probed = false;
    try {
      var c = document.createElement("canvas");
      var gl = c.getContext("webgl") || c.getContext("experimental-webgl");
      if (gl && typeof gl.createShader === "function") {
        probed = true;
        var lose = gl.getExtension("WEBGL_lose_context");
        if (lose) lose.loseContext();
      }
    } catch (e) { probed = false; }
    return probed;
  }

  function Renderer(canvas) {
    this.canvas = canvas;
    this.gl = null;
    this.bufs = {};
    this.texs = {};
    this.draws = 0;
    this.maxPoint = 64;
    this.ptBuf = null;
  }

  Renderer.prototype.init = function () {
    var gl = this.gl;
    if (!gl) {
      var attrs = { alpha: false, antialias: true, depth: true, premultipliedAlpha: true,
                    preserveDrawingBuffer: false };
      try {
        gl = this.canvas.getContext("webgl", attrs) ||
             this.canvas.getContext("experimental-webgl", attrs);
      } catch (e) { gl = null; }
      if (!gl) return false;
      this.gl = gl;
    }
    if (gl.isContextLost && gl.isContextLost()) return false;
    this.bufs = {};
    this.texs = {};
    this.ptBuf = null;
    this.lit = this.program(LIT_VS, LIT_FS);
    this.pt = this.program(PT_VS, PT_FS);
    if (!this.lit || !this.pt) return false;
    try {
      var r = gl.getParameter(gl.ALIASED_POINT_SIZE_RANGE);
      this.maxPoint = Math.max(8, Math.min(256, r ? r[1] : 64));
    } catch (e) { this.maxPoint = 64; }
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.disable(gl.CULL_FACE);
    return true;
  };

  Renderer.prototype.program = function (vs, fs) {
    var gl = this.gl;
    function sh(type, src) {
      var s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS) && !gl.isContextLost()) {
        if (window.console) console.warn("bench stage shader:", gl.getShaderInfoLog(s));
        return null;
      }
      return s;
    }
    var v = sh(gl.VERTEX_SHADER, vs), f = sh(gl.FRAGMENT_SHADER, fs);
    if (!v || !f) return null;
    var p = gl.createProgram();
    gl.attachShader(p, v);
    gl.attachShader(p, f);
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS) && !gl.isContextLost()) {
      if (window.console) console.warn("bench stage link:", gl.getProgramInfoLog(p));
      return null;
    }
    var info = { p: p, a: {}, u: {} };
    var na = gl.getProgramParameter(p, gl.ACTIVE_ATTRIBUTES);
    for (var i = 0; i < na; i++) {
      var ai = gl.getActiveAttrib(p, i);
      info.a[ai.name] = gl.getAttribLocation(p, ai.name);
    }
    var nu = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
    for (var j = 0; j < nu; j++) {
      var ui = gl.getActiveUniform(p, j);
      info.u[ui.name] = gl.getUniformLocation(p, ui.name);
    }
    return info;
  };

  Renderer.prototype.resize = function (w, h) {
    if (this.canvas.width !== w) this.canvas.width = w;
    if (this.canvas.height !== h) this.canvas.height = h;
  };

  Renderer.prototype.meshBufs = function (mesh) {
    var b = this.bufs[mesh.id];
    if (b) return b;
    var gl = this.gl;
    b = { pos: gl.createBuffer(), nrm: gl.createBuffer(), uv: gl.createBuffer(),
          idx: gl.createBuffer(), count: mesh.idx.length };
    gl.bindBuffer(gl.ARRAY_BUFFER, b.pos);
    gl.bufferData(gl.ARRAY_BUFFER, mesh.pos, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, b.nrm);
    gl.bufferData(gl.ARRAY_BUFFER, mesh.nrm, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, b.uv);
    gl.bufferData(gl.ARRAY_BUFFER, mesh.uv, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, b.idx);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, mesh.idx, gl.STATIC_DRAW);
    this.bufs[mesh.id] = b;
    return b;
  };

  Renderer.prototype.texture = function (rec) {
    var t = this.texs[rec.id];
    if (t) return t;
    var gl = this.gl;
    t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, rec.size, rec.size, 0, gl.RGBA,
                  gl.UNSIGNED_BYTE, rec.data);
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
    var aniso = gl.getExtension("EXT_texture_filter_anisotropic") ||
                gl.getExtension("WEBKIT_EXT_texture_filter_anisotropic");
    if (aniso) {
      // A ground seen at 50 degrees smears without it; four taps is the cheap middle.
      gl.texParameterf(gl.TEXTURE_2D, aniso.TEXTURE_MAX_ANISOTROPY_EXT,
                       Math.min(4, gl.getParameter(aniso.MAX_TEXTURE_MAX_ANISOTROPY_EXT)));
    }
    this.texs[rec.id] = t;
    return t;
  };

  /* Drops one texture's GPU copy, so swapping biomes does not hold every floor painted
     this session in video memory. */
  Renderer.prototype.forgetTexture = function (rec) {
    var t = this.texs[rec.id];
    if (t && this.gl) this.gl.deleteTexture(t);
    delete this.texs[rec.id];
  };

  Renderer.prototype.dispose = function () {
    var gl = this.gl;
    if (!gl || gl.isContextLost()) return;
    var k;
    for (k in this.bufs) {
      var b = this.bufs[k];
      gl.deleteBuffer(b.pos); gl.deleteBuffer(b.nrm); gl.deleteBuffer(b.uv); gl.deleteBuffer(b.idx);
    }
    for (k in this.texs) gl.deleteTexture(this.texs[k]);
    if (this.ptBuf) gl.deleteBuffer(this.ptBuf);
    this.bufs = {}; this.texs = {}; this.ptBuf = null;
  };

  /* One frame's shared state: camera, lights, exposure. */
  Renderer.prototype.begin = function (f) {
    var gl = this.gl;
    this.f = f;
    this.draws = 0;
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.clearColor(f.bg[0], f.bg[1], f.bg[2], 1);
    gl.depthMask(true);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    var L = this.lit, u = L.u;
    gl.useProgram(L.p);
    gl.uniformMatrix4fv(u.uViewProj, false, f.vp);
    gl.uniform3fv(u.uEye, f.eye);
    gl.uniform3fv(u.uAmb, f.amb);
    gl.uniform3fv(u.uKeyPos, f.keyPos);
    gl.uniform3fv(u.uKeyCol, f.keyCol);
    gl.uniform3fv(u.uFillDir, f.fillDir);
    gl.uniform3fv(u.uFillCol, f.fillCol);
    gl.uniform3fv(u.uGlowPos, f.glowPos);
    gl.uniform3fv(u.uGlowCol, f.glowCol);
    gl.uniform3fv(u.uFlarePos, f.flarePos);
    gl.uniform3fv(u.uFlareCol, f.flareCol);
    gl.uniform1f(u.uExposure, f.exposure);
    gl.uniform1f(u.uReveal, f.reveal);
    gl.uniform3fv(u.uBg, f.bg);
    gl.uniform2f(u.uRes, this.canvas.width, this.canvas.height);
    gl.uniform2fv(u.uFade, f.fade);
    gl.uniform1i(u.uTex, 0);
    this.blend = null;
  };

  Renderer.prototype.setBlend = function (mode) {
    if (this.blend === mode) return;
    var gl = this.gl;
    this.blend = mode;
    if (mode === "opaque") {
      gl.disable(gl.BLEND);
      gl.depthMask(true);
    } else if (mode === "fade") {
      // An opaque thing fading in or out: blended, but still writing depth, so a tool
      // lifting away does not show its own back wall through its front for 180ms.
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.depthMask(true);
    } else if (mode === "alpha") {
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.depthMask(false);
    } else {
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
      gl.depthMask(false);
    }
  };

  var DEF = { color: [1, 1, 1], alpha: 1, spec: 0.2, shin: 16, metal: 0, emit: [0, 0, 0],
              pattern: 0, patScale: 1, bump: 0, fresnel: 0, unlit: 0, radial: 0, ground: 0,
              uvScale: [1, 1] };

  function pick(m, k) { return m[k] === undefined ? DEF[k] : m[k]; }

  /* Draws one mesh. `range` is [firstIndex, indexCount] for an arc: ring meshes are built
     angle-major, so any contiguous index run is a contiguous stretch of arc, and a dial's
     band or a closing ring is a sub-range of one buffer rather than a mesh per value. */
  Renderer.prototype.draw = function (mesh, model, mat, alphaMul, glint, range) {
    var gl = this.gl, L = this.lit, u = L.u, a = L.a;
    var b = this.meshBufs(mesh);
    gl.uniformMatrix4fv(u.uModel, false, model);
    gl.uniformMatrix3fv(u.uNrmMat, false, M.normalMat(model));
    gl.uniform3fv(u.uColor, pick(mat, "color"));
    gl.uniform1f(u.uAlpha, pick(mat, "alpha") * alphaMul);
    gl.uniform1f(u.uSpec, pick(mat, "spec"));
    gl.uniform1f(u.uShin, pick(mat, "shin"));
    gl.uniform1f(u.uMetal, pick(mat, "metal"));
    gl.uniform3fv(u.uEmit, pick(mat, "emit"));
    gl.uniform1f(u.uPattern, pick(mat, "pattern"));
    gl.uniform1f(u.uPatScale, pick(mat, "patScale"));
    gl.uniform1f(u.uBump, pick(mat, "bump"));
    gl.uniform1f(u.uFresnel, pick(mat, "fresnel"));
    gl.uniform1f(u.uUnlit, pick(mat, "unlit"));
    gl.uniform1f(u.uRadial, pick(mat, "radial"));
    gl.uniform1f(u.uGround, pick(mat, "ground"));
    gl.uniform1f(u.uGlint, glint || 0);
    if (mat.tex) {
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.texture(mat.tex));
      gl.uniform1f(u.uUseTex, 1);
      gl.uniform2fv(u.uUvScale, pick(mat, "uvScale"));
    } else {
      gl.uniform1f(u.uUseTex, 0);
    }
    gl.bindBuffer(gl.ARRAY_BUFFER, b.pos);
    gl.enableVertexAttribArray(a.aPos);
    gl.vertexAttribPointer(a.aPos, 3, gl.FLOAT, false, 0, 0);
    if (a.aNrm !== undefined) {
      gl.bindBuffer(gl.ARRAY_BUFFER, b.nrm);
      gl.enableVertexAttribArray(a.aNrm);
      gl.vertexAttribPointer(a.aNrm, 3, gl.FLOAT, false, 0, 0);
    }
    if (a.aUv !== undefined) {
      gl.bindBuffer(gl.ARRAY_BUFFER, b.uv);
      gl.enableVertexAttribArray(a.aUv);
      gl.vertexAttribPointer(a.aUv, 2, gl.FLOAT, false, 0, 0);
    }
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, b.idx);
    var first = range ? range[0] : 0, count = range ? range[1] : b.count;
    if (count > 0) {
      gl.drawElements(gl.TRIANGLES, count, gl.UNSIGNED_SHORT, first * 2);
      this.draws++;
    }
  };

  /* Soft round points: particles, the Mix guide, the incision path. Interleaved as
     x, y, z, r, g, b, a, size. */
  Renderer.prototype.points = function (data, count, additive) {
    if (!count) return;
    var gl = this.gl, P = this.pt, f = this.f;
    var L = this.lit;
    gl.useProgram(P.p);
    gl.uniformMatrix4fv(P.u.uView, false, f.view);
    gl.uniformMatrix4fv(P.u.uProj, false, f.proj);
    gl.uniform1f(P.u.uPx, f.px);
    gl.uniform1f(P.u.uMaxPt, this.maxPoint);
    gl.uniform1f(P.u.uExposure, f.exposure);
    gl.uniform1f(P.u.uReveal, f.reveal);
    if (!this.ptBuf) this.ptBuf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, this.ptBuf);
    gl.bufferData(gl.ARRAY_BUFFER, data.subarray(0, count * 8), gl.DYNAMIC_DRAW);
    // The lit program's attributes may sit on the same slots; switch them off so a
    // stale enabled array does not outlive its buffer.
    for (var k in L.a) gl.disableVertexAttribArray(L.a[k]);
    gl.enableVertexAttribArray(P.a.aPos);
    gl.vertexAttribPointer(P.a.aPos, 3, gl.FLOAT, false, 32, 0);
    gl.enableVertexAttribArray(P.a.aCol);
    gl.vertexAttribPointer(P.a.aCol, 4, gl.FLOAT, false, 32, 12);
    gl.enableVertexAttribArray(P.a.aSize);
    gl.vertexAttribPointer(P.a.aSize, 1, gl.FLOAT, false, 32, 28);
    this.setBlend(additive ? "add" : "alpha");
    gl.drawArrays(gl.POINTS, 0, count);
    this.draws++;
    for (var j in P.a) gl.disableVertexAttribArray(P.a[j]);
    gl.useProgram(L.p);
  };

  K.Renderer = Renderer;
  K.supported = supported;
})();
