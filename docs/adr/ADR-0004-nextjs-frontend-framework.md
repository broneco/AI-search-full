# ADR-0002: Select Next.js with React & TypeScript as the Frontend Web Client

- Status: accepted
- Date: 2026-05-29
- Owners: USER, Antigravity Agent
- Supersedes: None
- Superseded by: None

## Context

We need to build a user-friendly, enterprise-ready web-based client interface for the AI Search Application. The interface must support key interactive features such as:
1. Grounded RAG Chat with highlightable page citations (e.g. split-screen UI showing chat on the left and the cited document page/viewer on the right).
2. Detailed search results with metadata filtering (e.g. filtering by department, document type, language).
3. Real-time document ingestion status dashboard.
4. Future enterprise authentication (Microsoft Entra ID login) and strategic integrations (such as Microsoft Teams and Outlook add-ins).

## Decision

We decide to:
1. Use **Next.js (with React and TypeScript)** as our primary client-side web application framework, developed in a separate `/frontend` directory in our workspace.
2. Build custom component designs using **Vanilla CSS (or Tailwind CSS)** adhering strictly to HSL tailored color schemes, dark mode compatibility, and smooth micro-animations to deliver a premium user experience.

## Options considered

### Option A: Next.js (Chosen)
- **Pros**:
  - Extremely customizable layout (enabling premium features like interactive side-by-side RAG workspace panels).
  - Production-ready scalability, routing, and fast load times.
  - Seamless future integrations with enterprise Microsoft Entra ID authentication.
  - Strong community, documentation, and TypeScript typing safety.
- **Cons**:
  - Requires Node.js/npm package environment.
  - Higher initial setup overhead and boilerplate compared to simple scripting solutions.

### Option B: Streamlit
- **Pros**:
  - Extremely fast to write (100% Python, zero JavaScript/TypeScript).
  - Built-in chat inputs and chat message components out-of-the-box.
  - Simple, single-process execution.
- **Cons**:
  - Primarily suited for data science prototyping, not tailored enterprise web products.
  - Extremely rigid layout grid (rendering split-screen PDF previewers or custom interactive citations is very difficult).
  - Implementing advanced multi-user sessions and enterprise Entra ID OAuth integrations is complex and fragile.

## Consequences

### Positive:
- The UI will feel highly custom, robust, responsive, and look premium.
- The stack is perfectly aligned with long-term productization (deployment to Azure Container Apps, Teams Client, Outlook Add-in).
- Static page optimizations and clean, separated React component files will keep code maintainable.

### Negative / trade-offs:
- Introduces another programming language (TypeScript/React) and runtime dependency (Node.js/npm) into the developer workspace.

## Implementation notes

* The frontend will be scaffolded in `frontend/` using non-interactive scripts (`npx create-next-app@latest`).
* It will communicate asynchronously with the FastAPI backend `/api` endpoints.
* Secrets and API endpoints will be configured in a frontend-specific `.env.local` file (never committed).

## Follow-ups

- [ ] Scaffold the Next.js project under `frontend/`.
- [ ] Implement typed API client contracts to communicate with the FastAPI backend.
- [ ] Build the interactive Chat and Source Citation preview split-panel UI.
