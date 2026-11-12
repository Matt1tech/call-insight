# Architecture

## 1. System overview

```mermaid
flowchart TB
    subgraph Data["Data (backend/data)"]
        TR[transcripts.json<br/>10 fictional calls]
        AN[analysis.json<br/>reviewed analysis]
    end

    subgraph AI["AI layer (app/ai)"]
        WF[LangGraph workflow<br/>12 nodes]
        PR[Prompt library<br/>system + node prompts]
        LLM[llm_client<br/>LangChain ChatOpenAI]
    end

    CF[(Cloudflare Workers AI<br/>live mode, untested)]

    subgraph Backend["FastAPI monolith (app)"]
        REPO[Repository<br/>load + validate JSON]
        SCH[Pydantic schemas<br/>allowed values]
        SVC[Analytics service<br/>filters + metrics]
        API[REST API /api]
    end

    UI[HTML dashboard<br/>frontend/ served at /]
    USER([User])

    TR --> WF
    PR --> WF
    WF -->|live mode| LLM --> CF
    WF -->|replay mode| AN
    AN --> REPO
    TR --> REPO
    SCH --> REPO
    REPO --> SVC --> API
    API --> UI --> USER
```

The demo uses the replay path: the analysis file is loaded, validated and served. The AI layer reproduces the same analysis through the graph and is run from `scripts/analyse.py`.

## 2. Analysis workflow (LangGraph)

```mermaid
flowchart TD
    A[prepare_transcript<br/>normalise turns t1..tn] --> B[classify_language]
    B --> C[classify_intent]
    C --> D[analyse_sentiment<br/>sentiment, emotion, tone]
    D --> E[assess_resolution<br/>status, urgency, escalation]
    E --> F[extract_evidence<br/>verbatim quotes + turns]
    F --> G[analyse_root_cause<br/>facts, assumptions, missing info]
    G --> H[predict_risks<br/>escalation, repeat contact]
    H --> I[recommend_action<br/>action, team, priority]
    I --> J[detect_knowledge_gaps<br/>unsupported claims, missing info]
    J --> K[summarise_and_score<br/>summary, confidence, flags]
    K --> L{validate_output<br/>Pydantic + verbatim evidence}
    L -->|valid| M([Analysis record])
    L -->|invalid, live mode| N[retry failing node once]
    N --> L
    L -->|still invalid| O([Record with errors noted])
```

## 3. How each node runs

```mermaid
flowchart LR
    S[Node] --> Q{Mode}
    Q -->|live| P[Prompt template<br/>+ transcript in tags]
    P --> M[Chat model<br/>structured output]
    M --> X[Slice model]
    Q -->|replay| R[Slice from<br/>analysis.json]
    R --> X
    X --> ST[(Graph state)]
```

## 4. Request flow in the dashboard

```mermaid
sequenceDiagram
    actor U as User
    participant B as Browser (app.js)
    participant F as FastAPI
    participant S as Analytics service
    participant R as Repository

    U->>B: Open http://localhost:8000
    B->>F: GET /
    F-->>B: index.html, styles.css, app.js
    B->>F: GET /api/filters
    B->>F: GET /api/analytics/overview?resolution=Unresolved
    F->>S: overview(filters)
    S->>R: all conversations
    R-->>S: validated records
    S-->>F: counts + calls
    F-->>B: JSON
    B-->>U: Render charts and call shelf
    U->>B: Click a call
    B->>F: GET /api/conversations/CALL-006
    F-->>B: transcript + full analysis
    B-->>U: Evidence, root cause, action, gaps
```

## 5. Resolution and satisfaction are separate

```mermaid
flowchart LR
    T[Transcript] --> RS{Outcome confirmed?}
    T --> SE{Beneficiary sentiment}
    RS -->|explicit confirmation| R1[Resolved]
    RS -->|material request open| R2[Unresolved]
    RS -->|cannot be confirmed| R3[Unknown]
    SE --> S1[Positive]
    SE --> S2[Neutral]
    SE --> S3[Negative]
    R1 & R2 & R3 --> MX[[Matrix view]]
    S1 & S2 & S3 --> MX
```

Example: CALL-006 has a fixed payment but an open service complaint, so it is Unresolved with Negative sentiment. A completed payment does not close a separate complaint.
