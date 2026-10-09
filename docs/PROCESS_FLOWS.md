# Process Flows

All flows are **planned** unless the roadmap evidence says otherwise.

## 1. Image ingestion
```mermaid
sequenceDiagram
  participant C as Client
  participant A as API
  participant V as Validator
  participant Q as Task queue
  C->>A: POST /v1/analyze
  A->>V: Check type, bytes, dimensions, pixels
  alt invalid
    V-->>A: invalid_input
    A-->>C: Error envelope
  else valid
    V->>Q: Enqueue (bounded)
    alt queue full
      Q-->>A: rejected
      A-->>C: resource_limit error
    else accepted
      Q-->>A: Task accepted
    end
  end
```

## 2. OCR
```mermaid
flowchart TD
  I[Decoded image] --> R{Provider available?}
  R -->|no| U[status unavailable]
  R -->|yes| P[Lazy-load model, run with timeout]
  P --> N[Normalize: text, confidence or null, bbox2d]
  P -->|error| E[Provider error in envelope]
  N --> OUT[OCR result]
```

## 3. Object detection (Phase 3)
```mermaid
flowchart TD
  I[Decoded image] --> R{Detector available?}
  R -->|no| U[status unavailable]
  R -->|yes| P[Resize, infer with timeout]
  P --> M[Map boxes back to original pixels]
  M --> N[Normalize: label, confidence or null, bbox2d]
  P -->|error| E[Provider error]
```

## 4. External AI request (Phase 4)
```mermaid
flowchart TD
  T[Task] --> POL{Policy permits external?}
  POL -->|no| LOC[Local or unavailable]
  POL -->|yes| CONS{Consent and credentials configured?}
  CONS -->|no| LOC
  CONS -->|yes| BUD{Within cost/quota limits?}
  BUD -->|no| ERR[quota_exceeded]
  BUD -->|yes| CALL[Call adapter with timeout]
  CALL -->|ok| OK[Normalize result]
  CALL -->|fail| RET{Retries left?}
  RET -->|yes| CALL
  RET -->|no| FB[Fallback or provider error]
```

## 5. Live camera (Phase 5)
```mermaid
flowchart LR
  CAM[Camera] --> S[Frame sampler] --> BQ[Bounded queue: drop oldest] --> INF[Inference worker] --> SC[Scene state] --> UI[Overlay]
  UI -->|cancel| INF
```
Capture and sampling never wait for external AI.

## 6. Voice request (Phase 6)
```mermaid
flowchart LR
  MIC[Audio] --> STT[STT provider] --> INT[Intent routing] --> CTX[Scene context lookup] --> LLM[LLM provider] --> OUT[Text and optional TTS]
```
Runs on a separate path from the vision loop.

## 7. Provider failure
```mermaid
flowchart TD
  F[Provider error] --> K{Retryable and budget left?}
  K -->|yes| R[Retry with backoff, bounded]
  K -->|no| FB{Fallback allowed by policy?}
  FB -->|yes| ALT[Try next provider]
  FB -->|no| ST[Capability status failed or unavailable]
  R --> F
```

## 8. Cancellation
```mermaid
flowchart TD
  X[Cancel request or client disconnect] --> Q{Task state}
  Q -->|queued| RM[Remove from queue: cancelled]
  Q -->|running| SIG[Set cancel flag, stop at next checkpoint or timeout]
  SIG --> CL[Release resources, cleanup temp files]
```

## 9. Future spatial processing (Phase 8+)
```mermaid
flowchart LR
  P[Valid pose, tracking, depth] --> T[Coordinate transform] --> V[Validated spatial target] --> A[Spatial anchor] --> PN[AR/MR panel]
  P -.->|any input missing| U[spatial not_implemented or unavailable]
```
