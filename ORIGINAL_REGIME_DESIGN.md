# Market Regime Trading Flow

```mermaid
flowchart TD
    A[Market Opens 9:15] --> B[Phase 1: Observe First 5-10 min]
    B --> C{Analyse Market Regime}
    
    C -->|100% one direction, strong momentum| D[STRONG TREND]
    C -->|Directional but slow, small range| E[SLOW TREND]
    C -->|Signals flipping, mixed direction| F[CHOPPY]
    C -->|Mostly neutral, no signals| G[FLAT]
    
    D --> D1["Target: 15-20pt<br/>SL: 10-12pt<br/>Lots: Max<br/>Re-entry: Aggressive"]
    E --> E1["Target: 8-10pt<br/>SL: 6-8pt<br/>Lots: Moderate<br/>Re-entry: Cautious"]
    F --> F1["Target: 3-5pt<br/>SL: 3-5pt<br/>Lots: Minimum<br/>Re-entry: None"]
    G --> G1["DON'T TRADE<br/>Wait for regime change"]
    
    D1 --> H[Execute Trades]
    E1 --> H
    F1 --> H
    G1 --> I
    
    H --> I{"Monitor Every 15 min:<br/>Has regime changed?"}
    
    I -->|Range expanding + same direction| J[Stay / Upgrade to STRONG]
    I -->|Range shrinking + direction holds| K[Downgrade to SLOW]
    I -->|Signals started flipping| L[Downgrade to CHOPPY]
    I -->|All signals went neutral| M[Switch to FLAT]
    I -->|No change| H
    
    J --> D1
    K --> E1
    L --> F1
    M --> G1
```

## Regime Definitions

- **STRONG TREND**
  - Target: 15-20 pt
  - Stop Loss: 10-12 pt
  - Lots: Maximum
  - Re-entry: Aggressive

- **SLOW TREND**
  - Target: 8-10 pt
  - Stop Loss: 6-8 pt
  - Lots: Moderate
  - Re-entry: Cautious

- **CHOPPY**
  - Target: 3-5 pt
  - Stop Loss: 3-5 pt
  - Lots: Minimum
  - Re-entry: None

- **FLAT**
  - Do not trade
  - Wait for regime change