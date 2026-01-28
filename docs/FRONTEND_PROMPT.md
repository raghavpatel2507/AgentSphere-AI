# Prompt: Build the AgentSphere-AI Frontend

**Role:** You are a Senior Frontend Architect and UI/UX Designer specializing in building "premium", high-performance AI interfaces.

**Objective:** Build a production-ready, aesthetically stunning React application for **AgentSphere-AI** that fully integrates with the existing FastAPI backend.

**Context:**
I have a fully functional FastAPI backend running at `http://localhost:8000`.
- API Documentation is located at: `docs/API_DOCUMENTATION.md`
- Backend Setup is located at: `docs/BACKEND_SETUP.md`
- The backend handles Authentication (JWT), Chat (SSE Streaming), MCP Server Management, and Human-in-the-Loop (HITL) approvals.

---

## 1. Technology Stack (Strict Requirements)

- **Framework:** Vite + React (TypeScript)
- **Styling:** Tailwind CSS (v4 if stable, else v3.4)
- **UI Library:** Shadcn UI (Radix Primitives)
- **Icons:** Lucide React
- **State Management:** Zustand (for global store), TanStack Query (for API caching)
- **Forms:** React Hook Form + Zod
- **Animations:** Framer Motion (Essential for the "premium" feel)
- **Markdown:** React Markdown + Syntax Highlighter (for AI responses)
- **Connectivity:** `axios` (API requests), `eventsource-parser` (SSE streaming)

---

## 2. Design Aesthetics ("The Wow Factor")

The design must feel **futuristic, professional, and fluid**.
- **Theme:** Default Dark Mode. Deep midnight blues/blacks (`#0a0a0a`), not just flat grey.
- **Glassmorphism:** Use subtle blur effects on sidebars, modals, and floating headers.
- **Typography:** Inter or Geist Sans. Clean, legible, professional.
- **Micro-interactions:**
    - Buttons should have subtle glow on hover.
    - Modals should scale in gently.
    - Chat messages should fade in.
    - Status indicators (e.g., "Connecting to MCP...") should pulse.

---

## 3. Architecture & Project Structure

Use a **Feature-based architecture** to keep code modular and clean.

```
src/
├── api/                # Axios instance, interceptors (auth token injection)
├── components/         # Shared UI components (Button, Input, Modal)
│   └── ui/             # Shadcn components
├── features/
│   ├── auth/           # Login, Register, Profile forms
│   ├── chat/           # Chat interface, Message bubbles, Input area
│   ├── mcp/            # Server list, Tool toggles, Configuration forms
│   └── hitl/           # Approval request cards
├── hooks/              # Custom hooks (useAuth, useStream)
├── layouts/            # DashboardLayout, AuthLayout
├── lib/                # Utils (cn, formatters)
├── stores/             # Zustand stores (authStore, settingsStore)
└── types/              # TypeScript interfaces (matching backend models)
```

---

## 4. Key Features & Implementation Details

### A. Authentication & Routing
- **Routes:**
    - `/login`, `/register`: Public routes.
    - `/`: Protected Dashboard (redirects to Login if no token).
- **Logic:**
    - Store JWT in `localStorage` + Zustand.
    - Axios interceptor: Auto-attach `Authorization: Bearer <token>`.
    - Auto-redirect on 401 Unauthorized.

### B. Core Layout (Dashboard)
- **Sidebar (Left):**
    - User Profile (Avatar + Settings).
    - Navigation: "Chats", "MCP Servers", "Registry", "Approvals" (Badge for pending HITL).
    - "New Chat" button (prominent).
    - Recent Conversation History list (infinite scroll).
- **Main Content:** Dynamic router outlet.

### C. Chat Interface (The Core Experience)
- **Streaming:**
    - Connect to `/api/v1/chat/{thread_id}/message` using SSE.
    - Handle events: `token` (append text), `tool_start` (show "Using tool..."), `tool_end` (show collapsible result), `approval_required` (show HITL card).
    - **Visuals:**
        - User message: Right aligned, distinct color.
        - AI message: Left aligned, markdown rendering.
        - **Tool Execution:** Don't dump raw JSON. Show a sleek "Thinking..." accordion. When formatted, show inputs/outputs cleanly.
- **Input Area:**
    - Textarea (auto-resize).
    - Send button (disabled while streaming).
    - Stop Generation button (appears while streaming).

### D. MCP Manager
- **Server List:** Cards showing Server Name, Status (Enabled/Disabled), Tool Count.
- **Add Server:** Modal form to JSON config (env vars, command).
- **Tool Browser:** Click a server -> view list of tools -> Toggle Enable/Disable per tool.

### E. Human-in-the-Loop (HITL) Dashboard
- **Notification:** Real-time alert when `approval_required` event occurs in chat.
- **Approval Card:**
    - Shows: Tool Name, Arguments (formatted JSON), Risk Level.
    - Actions: "Approve", "Reject", "Approve & Whitelist".
    - Visual: Warning colors (Amber/Yellow).

---

## 5. Implementation Steps (Order of Execution)

1.  **Scaffold:** Initialize Vite project, setup Tailwind, install dependencies (`shadcn-ui`, `axios`, `zustand`, `framer-motion`).
2.  **API Layer:** Create `src/api/client.ts` with Axios interceptors for JWT.
3.  **Auth Feature:** Build Login/Register pages and `useAuth` hook. Verify against `/api/v1/auth`.
4.  **Layout:** Build the Dashboard Shell (Sidebar + Router).
5.  **MCP Feature:** Build Server List and Add Server Modal. Verify against `/api/v1/mcp`.
6.  **Chat Feature:** Implement the Chat UI and SSE logic. Handle `token` streaming first, then `tool` events.
7.  **HITL Feature:** Add the Approval UI for `approval_required` events.
8.  **Polish:** Add Framer Motion animations to page transitions and message appearance.

---

**Resources to Use:**
- Refer to `docs/API_DOCUMENTATION.md` for endpoint contracts.
- Use `docs/BACKEND_SETUP.md` to ensure backend is running.

**Action:**
Start by scaffolding the project structure and setting up the API client with Authentication. Then proceed to the Layout.
