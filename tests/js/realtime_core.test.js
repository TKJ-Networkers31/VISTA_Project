"use strict";
// Run: node --test tests/js/        (Node 18+; no packages needed)
const test = require("node:test");
const assert = require("node:assert/strict");
const RT = require("../../apps/web/static/realtime_core.js");

const flush = () => new Promise((r) => setImmediate(r));

function makeClock() {
  let t = 0;
  let id = 0;
  const timers = new Map();
  return {
    now: () => t,
    setTimer: (f, ms) => {
      const k = ++id;
      timers.set(k, { f, at: t + ms });
      return k;
    },
    clearTimer: (k) => timers.delete(k),
    pending: () => timers.size,
    async advance(ms) {
      const end = t + ms;
      for (;;) {
        await flush();
        let next = null;
        for (const [k, v] of timers) if (v.at <= end && (!next || v.at < next.v.at)) next = { k, v };
        if (!next) break;
        timers.delete(next.k);
        t = Math.max(t, next.v.at);
        next.v.f();
      }
      await flush();
      t = end;
    },
  };
}

function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => ((resolve = a), (reject = b)));
  return { promise, resolve, reject };
}

// ---------------- geometry ----------------
test("containRect: letterbox and pillarbox", () => {
  const wide = RT.containRect(640, 360, 800, 800);
  assert.equal(wide.scale, 1.25);
  assert.deepEqual([wide.x, wide.y, wide.width, wide.height], [0, 175, 800, 450]);
  const tall = RT.containRect(640, 360, 1000, 300);
  assert.ok(Math.abs(tall.scale - 300 / 360) < 1e-9);
  assert.ok(Math.abs(tall.x - (1000 - 640 * (300 / 360)) / 2) < 1e-9 && tall.y === 0);
  assert.equal(RT.containRect(0, 360, 800, 800), null);
  assert.equal(RT.containRect(640, 360, 0, 800), null);
});

test("mapBox: same box maps identically whatever frame size was sent", () => {
  const rect = RT.containRect(640, 360, 800, 800);
  const a = RT.mapBox([64, 36, 128, 72], 640, 360, rect);
  const b = RT.mapBox([32, 18, 64, 36], 320, 180, rect); // same box in a half-size frame
  assert.deepEqual(a, { x: 80, y: 220, w: 80, h: 45 });
  assert.deepEqual(b, a);
});

test("mapBox: stays proportional when the container is resized", () => {
  const box = [100, 50, 300, 150];
  for (const [cw, ch] of [[800, 450], [400, 225], [1000, 300], [300, 900]]) {
    const rect = RT.containRect(640, 360, cw, ch);
    const m = RT.mapBox(box, 640, 360, rect);
    assert.ok(Math.abs((m.x - rect.x) / rect.width - 100 / 640) < 1e-9);
    assert.ok(Math.abs((m.y - rect.y) / rect.height - 50 / 360) < 1e-9);
    assert.ok(Math.abs(m.w / rect.width - 200 / 640) < 1e-9);
    assert.ok(Math.abs(m.h / rect.height - 100 / 360) < 1e-9);
  }
});

test("mapBox rejects invalid input", () => {
  const rect = RT.containRect(640, 360, 800, 450);
  assert.equal(RT.mapBox([1, 2, 3], 640, 360, rect), null);
  assert.equal(RT.mapBox([5, 5, 5, 9], 640, 360, rect), null);
  assert.equal(RT.mapBox([0, 0, NaN, 9], 640, 360, rect), null);
  assert.equal(RT.mapBox([0, 0, 9, 9], 0, 360, rect), null);
  assert.equal(RT.mapBox([0, 0, 9, 9], 640, 360, null), null);
});

test("captureSize keeps aspect ratio and never upscales", () => {
  assert.deepEqual(RT.captureSize(1920, 1080, 640), { width: 640, height: 360 });
  assert.deepEqual(RT.captureSize(1080, 1920, 640), { width: 360, height: 640 });
  assert.deepEqual(RT.captureSize(320, 240, 640), { width: 320, height: 240 });
  assert.equal(RT.captureSize(0, 240, 640), null);
  assert.equal(RT.captureSize(640, 480, NaN), null);
});

// ---------------- response validation / error text ----------------
const good = () => ({
  status: "succeeded", image_width: 640, image_height: 360,
  detections: [{ class_id: 0, label: "person", confidence: 0.8, bbox2d: [1, 2, 100, 200] }],
});

test("validateResponse accepts a valid body and rejects broken ones", () => {
  assert.equal(RT.validateResponse(good()).ok, true);
  assert.equal(RT.validateResponse(null).ok, false);
  assert.equal(RT.validateResponse({ ...good(), status: "failed" }).ok, false);
  assert.equal(RT.validateResponse({ ...good(), image_width: 0 }).ok, false);
  assert.equal(RT.validateResponse({ ...good(), detections: "x" }).ok, false);
  const bad = (patch) => {
    const b = good();
    Object.assign(b.detections[0], patch);
    return RT.validateResponse(b).ok;
  };
  assert.equal(bad({ confidence: 1.2 }), false);
  assert.equal(bad({ confidence: NaN }), false);
  assert.equal(bad({ label: 5 }), false);
  assert.equal(bad({ bbox2d: [1, 2, 3] }), false);
  assert.equal(bad({ bbox2d: [10, 2, 5, 9] }), false);
  assert.equal(bad({ bbox2d: [0, 0, 641, 9] }), false);
});

test("describeCameraError covers the main DOMException names", () => {
  assert.match(RT.describeCameraError({ name: "NotAllowedError" }), /permission was denied/i);
  assert.match(RT.describeCameraError({ name: "NotFoundError" }), /No camera/);
  assert.match(RT.describeCameraError({ name: "NotReadableError" }), /in use/);
  assert.match(RT.describeCameraError({ name: "OverconstrainedError" }), /selected camera/);
  assert.match(RT.describeCameraError({ name: "Weird" }), /Weird/);
});

test("describeBackendError maps timeout, network, 503 and invalid responses", () => {
  assert.match(RT.describeBackendError(new RT.RTError("timeout", "x")).message, /did not answer/);
  assert.match(RT.describeBackendError(new RT.RTError("network", "x")).message, /Cannot reach/);
  assert.match(RT.describeBackendError(new RT.RTError("http", "m", { status: 503, code: "DETECTOR_UNAVAILABLE" })).message, /not ready/);
  assert.match(RT.describeBackendError(new RT.RTError("invalid", "bad bbox")).message, /bad bbox/);
});

// ---------------- statistics ----------------
test("median and rate meter", () => {
  assert.equal(RT.median([]), null);
  assert.equal(RT.median([5, 1, 3]), 3);
  assert.equal(RT.median([1, 2, 3, 4]), 2.5);
  const clock = makeClock();
  const m = RT.createRateMeter(5000, clock.now);
  assert.equal(m.rate(), null);
  m.mark();
  return clock.advance(500).then(async () => {
    m.mark();
    await clock.advance(500);
    m.mark();
    assert.equal(m.rate(), 2); // 2 intervals in 1 s
    await clock.advance(10000);
    assert.equal(m.rate(), null); // stale marks are dropped, no invented number
  });
});

// ---------------- detection loop ----------------
function harness(opts = {}) {
  const clock = makeClock();
  const h = { clock, starts: [], concurrent: 0, maxConcurrent: 0, results: [], errors: [], pending: [] };
  h.send = opts.send || ((frame, signal) => {
    const d = deferred();
    h.pending.push({ d, signal, frame });
    return d.promise;
  });
  h.loop = RT.createDetectionLoop({
    fps: opts.fps || 2, now: clock.now, setTimer: clock.setTimer, clearTimer: clock.clearTimer,
    capture: opts.capture || (async () => "frame"),
    send: async (frame, signal) => {
      h.starts.push(clock.now());
      h.concurrent++;
      h.maxConcurrent = Math.max(h.maxConcurrent, h.concurrent);
      try {
        return await h.send(frame, signal);
      } finally {
        h.concurrent--;
      }
    },
    onResult: (r, info) => h.results.push([r, info]),
    onError: (e, info) => h.errors.push([e, info]),
  });
  return h;
}

test("loop: fast backend is paced to the target FPS", async () => {
  const h = harness({ fps: 2, send: async () => "ok" });
  h.loop.start();
  await h.clock.advance(5000);
  assert.ok(h.starts.length >= 9 && h.starts.length <= 11, String(h.starts.length));
  for (let i = 1; i < h.starts.length; i++) assert.ok(h.starts[i] - h.starts[i - 1] >= 500);
  h.loop.stop();
});

test("loop: slow backend never gets overlapping requests", async () => {
  const h = harness({ fps: 5 });
  h.loop.start();
  await h.clock.advance(3000);
  assert.equal(h.starts.length, 1); // still waiting for request #1; nothing piles up
  h.pending[0].d.resolve("r1");
  await h.clock.advance(1);
  assert.equal(h.results.length, 1);
  assert.equal(h.starts.length, 2); // late request: next one starts immediately, not queued meanwhile
  assert.equal(h.maxConcurrent, 1);
  h.loop.stop();
});

test("loop: stop() aborts the request and drops its late result", async () => {
  const h = harness();
  h.loop.start();
  await h.clock.advance(1);
  const first = h.pending[0];
  h.loop.stop();
  assert.equal(first.signal.aborted, true);
  first.d.resolve("late");
  await h.clock.advance(5000);
  assert.equal(h.results.length, 0);
  assert.equal(h.loop.stats().stale, 1);
  assert.equal(h.clock.pending(), 0); // no timer left behind
});

test("loop: pause/resume while a request is in flight does not duplicate the loop", async () => {
  const h = harness({ fps: 5 });
  h.loop.start();
  await h.clock.advance(1);
  h.loop.stop();
  h.loop.start();
  h.loop.stop();
  h.loop.start(); // rapid toggling
  await h.clock.advance(2000);
  assert.equal(h.starts.length, 1); // old request still pending: no second one
  h.pending[0].d.resolve("stale-result");
  await h.clock.advance(1);
  assert.equal(h.starts.length, 2);
  assert.equal(h.results.length, 0); // the old result belongs to an earlier generation
  h.pending[1].d.resolve("fresh");
  await h.clock.advance(1);
  assert.deepEqual(h.results.map((r) => r[0]), ["fresh"]);
  assert.equal(h.maxConcurrent, 1);
  h.loop.stop();
});

test("loop: errors never end the loop; backoff is bounded and resets on success", async () => {
  const outcomes = [new Error("a"), new Error("b"), new Error("c"), "ok", "ok"];
  let i = 0;
  const h = harness({
    fps: 10,
    send: async () => {
      const o = outcomes[i++];
      if (o instanceof Error) throw o;
      return o;
    },
  });
  h.loop.start();
  await h.clock.advance(4000);
  const gaps = h.starts.slice(1, 5).map((t, k) => t - h.starts[k]);
  assert.deepEqual(gaps, [350, 600, 1100, 100]); // 100 ms pacing + 250/500/1000 backoff, then reset
  assert.deepEqual(h.errors.map((e) => e[1].consecutiveErrors), [1, 2, 3]);
  assert.equal(h.loop.isActive(), true);
  h.loop.stop();
});

test("loop: unready video (null frame) is skipped, not sent", async () => {
  let n = 0;
  const h = harness({ fps: 10, send: async () => "ok", capture: async () => (n++ < 2 ? null : "frame") });
  h.loop.start();
  await h.clock.advance(1000);
  assert.equal(h.loop.stats().skipped, 2);
  assert.ok(h.starts.length >= 1);
  h.loop.stop();
});

test("loop: a throwing onError callback does not kill the loop", async () => {
  const clock = makeClock();
  let sends = 0;
  const loop = RT.createDetectionLoop({
    fps: 10, now: clock.now, setTimer: clock.setTimer, clearTimer: clock.clearTimer,
    capture: async () => "f", send: async () => { sends++; throw new Error("x"); },
    onResult() {}, onError() { throw new Error("ui bug"); },
  });
  loop.start();
  await clock.advance(3000);
  assert.ok(sends >= 2);
  loop.stop();
});

// ---------------- camera controller ----------------
function fakeTrack() {
  const t = { stopped: 0, handlers: {} };
  t.stop = () => t.stopped++;
  t.addEventListener = (n, f) => (t.handlers[n] = f);
  t.removeEventListener = (n) => delete t.handlers[n];
  return t;
}
function fakeStream(n = 1) {
  const tracks = Array.from({ length: n }, fakeTrack);
  return { tracks, getTracks: () => tracks, getVideoTracks: () => tracks };
}
function camHarness(getUserMedia) {
  const video = { srcObject: null, play: async () => {} };
  const states = [];
  let ended = 0;
  const cam = RT.createCameraController({
    mediaDevices: getUserMedia === undefined ? undefined : { getUserMedia },
    video, onChange: (s) => states.push(s), onEnded: () => ended++,
  });
  return { cam, video, states, ended: () => ended };
}

test("camera: start attaches the stream, stop stops every track and detaches", async () => {
  const stream = fakeStream(2);
  const h = camHarness(async () => stream);
  assert.deepEqual(await h.cam.start(), { ok: true });
  assert.equal(h.video.srcObject, stream);
  assert.equal(h.cam.getState(), "on");
  h.cam.stop();
  assert.deepEqual(stream.tracks.map((t) => t.stopped), [1, 1]);
  assert.equal(h.video.srcObject, null);
  assert.equal(h.cam.getState(), "off");
  assert.deepEqual(h.states, ["starting", "on", "off"]);
});

test("camera: the selected deviceId is requested as exact, audio is off", async () => {
  let seen;
  const h = camHarness(async (c) => ((seen = c), fakeStream()));
  await h.cam.start("abc123");
  assert.deepEqual(seen.video.deviceId, { exact: "abc123" });
  assert.equal(seen.audio, false);
  h.cam.stop();
});

test("camera: permission denied, not found, not readable give clear errors and no stream", async () => {
  for (const [name, re] of [["NotAllowedError", /permission was denied/i], ["NotFoundError", /No camera/], ["NotReadableError", /in use/]]) {
    const h = camHarness(async () => { throw Object.assign(new Error("x"), { name }); });
    const r = await h.cam.start();
    assert.equal(r.ok, false);
    assert.match(r.message, re);
    assert.equal(h.cam.getState(), "error");
    assert.equal(h.video.srcObject, null);
  }
});

test("camera: missing mediaDevices (insecure context) is reported", async () => {
  const h = camHarness(undefined);
  const r = await h.cam.start();
  assert.equal(r.ok, false);
  assert.match(r.message, /secure context/);
});

test("camera: stop() while the permission prompt is open still releases the stream", async () => {
  const d = deferred();
  const h = camHarness(() => d.promise);
  const p = h.cam.start();
  h.cam.stop();
  const stream = fakeStream();
  d.resolve(stream);
  assert.equal((await p).ok, false);
  assert.equal(stream.tracks[0].stopped, 1);
  assert.equal(h.video.srcObject, null);
  assert.equal(h.cam.getState(), "off");
});

test("camera: a second start() while on or starting does not open another stream", async () => {
  let calls = 0;
  const h = camHarness(async () => (calls++, fakeStream()));
  await Promise.all([h.cam.start(), h.cam.start()]);
  await h.cam.start();
  assert.equal(calls, 1);
  h.cam.stop();
});

test("camera: unplugging the device stops the controller and notifies", async () => {
  const stream = fakeStream();
  const h = camHarness(async () => stream);
  await h.cam.start();
  stream.tracks[0].handlers.ended();
  assert.equal(h.cam.getState(), "off");
  assert.equal(h.ended(), 1);
  assert.equal(stream.tracks[0].stopped, 1);
});

test("camera: restart after stop opens a fresh stream (no leak from the first)", async () => {
  const streams = [fakeStream(), fakeStream()];
  let i = 0;
  const h = camHarness(async () => streams[i++]);
  await h.cam.start();
  h.cam.stop();
  await h.cam.start();
  assert.equal(streams[0].tracks[0].stopped, 1);
  assert.equal(streams[1].tracks[0].stopped, 0);
  h.cam.stop();
  assert.equal(streams[1].tracks[0].stopped, 1);
});
