// k6 WebSocket load test for DeepTutor face B — /api/v1/chat (the path MathVerse uses).
//
// Purpose: establish the concurrency → latency → error-rate BASELINE that the
// high-concurrency roadmap (P0) calls for, and to re-run after each phase to
// prove the curve moved. Measures time-to-first-token (TTFT) and time-to-result.
//
// Run against the INTERNAL DeepTutor instance (never the public edge). Auth is a
// no-op when the engine runs ENABLE_AUTH=false (docker default), so no token.
//
//   # on the server, against the container:
//   TARGET=ws://127.0.0.1:8001 k6 run load-tests/deeptutor-chat-ws.js
//   # ramp shape / volume overrides:
//   TARGET=ws://127.0.0.1:8001 VUS=200 DURATION=2m k6 run load-tests/deeptutor-chat-ws.js
//
// Output: per-stage VU count plus p50/p95/p99 for ttft_ms and result_ms, and the
// turn_error rate. Sweep VUS (e.g. 10,25,50,100,200,400) to find the knee.

import ws from 'k6/ws';
import { check } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const TARGET = __ENV.TARGET || 'ws://127.0.0.1:8001';
const VUS = parseInt(__ENV.VUS || '50', 10);
const DURATION = __ENV.DURATION || '1m';
const TURN_TIMEOUT_MS = parseInt(__ENV.TURN_TIMEOUT_MS || '120000', 10);

const ttft = new Trend('ttft_ms', true);       // time to first stream token
const resultMs = new Trend('result_ms', true);  // time to terminal result
const turnError = new Rate('turn_error');
const turnsDone = new Counter('turns_completed');

// A small pool of real-ish math prompts so we don't hammer one cached answer.
const PROMPTS = [
  '求极限 lim(x->0) (sin x - x) / x^3。',
  '计算定积分 ∫_0^1 x e^{x} dx。',
  '求矩阵 [[2,1],[1,2]] 的特征值与特征向量。',
  '解方程 x^2 - 5x + 6 = 0，并说明判别式。',
  '一枚均匀硬币抛 3 次，求恰好两次正面的概率。',
];

export const options = {
  scenarios: {
    ramp_hold: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '15s', target: VUS },   // ramp up
        { duration: DURATION, target: VUS }, // hold at target concurrency
        { duration: '10s', target: 0 },      // ramp down
      ],
      gracefulStop: '30s',
    },
  },
  thresholds: {
    turn_error: ['rate<0.02'],     // <2% failed turns
    result_ms: ['p(95)<60000'],    // p95 full solve under 60s (tune to your model)
  },
};

export default function () {
  const url = `${TARGET}/api/v1/chat`;
  const prompt = PROMPTS[Math.floor(Math.random() * PROMPTS.length)];
  const t0 = Date.now();
  let firstTokenAt = 0;
  let gotResult = false;

  const res = ws.connect(url, {}, function (socket) {
    socket.on('open', function () {
      socket.send(JSON.stringify({ message: prompt, language: 'zh' }));
    });

    socket.on('message', function (raw) {
      let ev;
      try { ev = JSON.parse(raw); } catch (_) { return; }
      const type = ev.type;
      if (type === 'stream' && firstTokenAt === 0) {
        firstTokenAt = Date.now();
        ttft.add(firstTokenAt - t0);
      } else if (type === 'result') {
        gotResult = true;
        resultMs.add(Date.now() - t0);
        turnsDone.add(1);
        socket.close();
      } else if (type === 'error') {
        turnError.add(true);
        socket.close();
      }
    });

    socket.setTimeout(function () {
      // No terminal result within the budget → count as a failed turn.
      if (!gotResult) { turnError.add(true); }
      socket.close();
    }, TURN_TIMEOUT_MS);

    socket.on('close', function () {
      if (gotResult) { turnError.add(false); }
    });
  });

  check(res, { 'ws handshake 101': (r) => r && r.status === 101 });
  if (!res || res.status !== 101) { turnError.add(true); }
}
