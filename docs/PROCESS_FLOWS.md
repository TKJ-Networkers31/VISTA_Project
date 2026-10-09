# Process Flows

All flows below are **planned** unless the roadmap says otherwise.

## 1. Image upload and analysis
```mermaid
sequenceDiagram
  participant U as User
  participant W as Web UI
  participant A as API
  participant P as Pipeline
  U->>W: Select image
  W->>A: POST /v1/analyze
  A->>A: Validate type, size, pixels
  A->>P: Decoded image
  P->>P: OCR and detection
  P-->>A: Normalized result
  A-->>W: JSON response
  W-->>U: Overlay and lists
```

## 2. OCR
```mermaid
flowchart TD
  I[Decoded image] --> PRE[Preprocess] --> OCR[OCR provider] --> NORM[Normalize text, confidence, bbox] --> OUT[OcrResult]
  OCR -->|error| ERR[status failed with error code]
```
Confidence is `null` if the provider gives none. Text is untrusted content (see prompt-injection notes in security doc).

## 3. Object detection
```mermaid
flowchart TD
  I[Decoded image] --> PRE[Resize for model] --> DET[Detector] --> MAP[Map boxes to original pixels] --> NORM[Normalize label, confidence, bbox] --> OUT[DetectionResult]
  DET -->|error| ERR[status failed]
```

## 4. Real-time camera (Phase 6)
```mermaid
flowchart LR
  CAM[Camera] --> CAP[Frame capture] --> Q[Bounded queue, drop oldest] --> INF[Inference] --> TRK[Tracking] --> ST[Scene state] --> UI[Overlay]
```

## 5. Voice to AI to speech (Phase 7)
```mermaid
flowchart LR
  MIC[Voice input] --> STT[Speech-to-text] --> ASSOC[Target association from scene state] --> LLM[LLM] --> OUT[Text, TTS, or info panel]
```
Runs in parallel with flow 4; vision never waits for the LLM.

## 6. Spatial tracking and AR/MR (Phases 8–9)
```mermaid
flowchart LR
  POSE[Pose, tracking, depth] --> TF[Coordinate transform] --> TGT[Validated spatial target] --> ANC[Spatial anchor] --> PANEL[AR/MR panel]
```
If any input is missing the result is `spatial.status = "unavailable"`; 2D boxes are never promoted to 3D.

## 7. Error handling and fallback
```mermaid
flowchart TD
  REQ[Request] --> VAL{Valid?}
  VAL -->|no| E1[Structured 4xx error]
  VAL -->|yes| RUN[Run capabilities]
  RUN --> OK{All ok?}
  OK -->|yes| R200[200 full result]
  OK -->|partial| R200P[200 with per-capability failed status]
  OK -->|all failed| E5[Structured 5xx error]
```
