# 🚀 AI-Powered Development Workflow Playbook

> **Goal:** Maximize AI usage across the full SDLC — from Jira ticket → Figma design → API integration → Code → Testing → Deployment.

---

## 📌 Overview: The AI-First Pipeline

```
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐
│  JIRA    │───▶│  FIGMA   │───▶│  API DOCS │───▶│  CODE    │───▶│  TEST &  │
│  Ticket  │    │  Design  │    │  Contract │    │  (AI)    │    │  DEPLOY  │
└──────────┘    └──────────┘    └───────────┘    └──────────┘    └──────────┘
     │               │               │                │               │
  AI helps:      AI helps:       AI helps:        AI helps:       AI helps:
  - Break down   - Extract       - Generate       - Full code     - Unit tests
    stories        specs           types/models     generation    - Integration
  - Write ACs    - Component     - Service layer  - Refactoring    tests
  - Estimate      list           - Mock data      - Bug fixes    - CI/CD
```

---

## 1️⃣ JIRA → AI (Planning & Requirements)

### What You Can Do
| Action | How to Use AI | Prompt Example |
|--------|---------------|----------------|
| Break down Epic into Stories | Paste epic description into AI | *"Break this epic into user stories with acceptance criteria: [paste epic]"* |
| Write Acceptance Criteria | Give AI the story title | *"Write detailed acceptance criteria for: User should be able to filter products by category"* |
| Estimate Story Points | Share story + ACs with AI | *"Estimate story points (fibonacci) for this story considering a mid-level team: [paste story]"* |
| Write Technical Approach | Share requirements | *"Write a technical approach document for implementing [feature] using React + Node.js"* |
| Create Sub-tasks | Share story details | *"Break this user story into developer sub-tasks: [paste story]"* |

### 🔧 Tools to Use
- **GitHub Copilot Chat** (in VS Code) — paste Jira ticket text and ask for breakdown
- **Copilot in Jira** (via browser extension) — draft descriptions directly
- **Any AI Chat** — for planning and estimation

### 💡 Pro Tip
> Copy the **entire Jira ticket** (title + description + ACs) into AI before starting any coding. This gives AI full context.

---

## 2️⃣ FIGMA → AI (Design to Code)

### What You Can Do
| Action | How to Use AI | Tool/Method |
|--------|---------------|-------------|
| Extract component list from design | Screenshot Figma frame → paste in AI | Copilot Vision / Claude |
| Generate component code from design | Share Figma screenshot | *"Generate a React component matching this design"* |
| Extract design tokens | Share Figma styles | *"Extract colors, fonts, spacing as CSS variables from this design"* |
| Generate responsive layouts | Describe the layout | *"Create a responsive grid layout: 3 columns on desktop, 1 on mobile"* |
| Convert design to HTML/CSS | Screenshot + describe | *"Convert this design to Tailwind CSS"* |

### 🔧 Tools & Workflow
1. **Figma Dev Mode** → Inspect components, get measurements
2. **Screenshot** the Figma frame → Paste into **GitHub Copilot Chat** (supports images)
3. Ask AI to generate the component code
4. Iterate: *"Make the button rounded"*, *"Add hover state"*, etc.

### 💡 Pro Tip
> Use **Figma's "Copy as CSS"** feature + AI to speed up styling. Paste the CSS into AI and ask it to convert to your framework (Tailwind, Styled Components, etc.)

---

## 3️⃣ API DOCS → AI (Service Layer Generation)

### What You Can Do
| Action | How to Use AI | Prompt Example |
|--------|---------------|----------------|
| Generate TypeScript types from API | Paste API response JSON | *"Generate TypeScript interfaces from this API response: [paste JSON]"* |
| Create API service layer | Share endpoint docs | *"Create an API service class for these endpoints: [paste docs]"* |
| Generate Axios/Fetch wrappers | Share API contract | *"Generate a typed Axios service for this REST API with error handling"* |
| Create mock data | Share API response shape | *"Generate realistic mock data matching this API schema"* |
| Generate API documentation | Share code | *"Generate OpenAPI/Swagger docs for these endpoints"* |

### 🔧 Workflow: API Docs → Code
```
Step 1: Copy API endpoint documentation (URL, method, request/response body)
Step 2: Paste into GitHub Copilot Chat
Step 3: Ask: "Generate a complete service file with types, API calls, and error handling"
Step 4: Ask: "Generate mock data for testing"
Step 5: Ask: "Generate unit tests for this service"
```

### 💡 Pro Tip
> If you have a **Swagger/OpenAPI spec file**, drop it in your repo. Then tell AI:
> *"Read the swagger.json and generate typed API services for all endpoints"*

---

## 4️⃣ CODE GENERATION (The Core Workflow)

### A. Starting a New Feature (using Copilot in VS Code)

#### Step-by-Step Process:
```
1. Open VS Code with your repo
2. Open GitHub Copilot Chat (Ctrl+Shift+I / Cmd+Shift+I)
3. Paste the FULL context:
   - Jira ticket description
   - API endpoint details
   - Figma component description
4. Ask AI to generate the code
5. Review, iterate, and refine
```

#### Key Prompts for Code Generation:
| Task | Prompt |
|------|--------|
| New Component | *"Create a React component for [feature] that fetches data from [API endpoint] and displays it as [describe UI]"* |
| New API Route | *"Create an Express/Next.js API route for [endpoint] that [describe logic]"* |
| Database Model | *"Create a Mongoose/Prisma model for [entity] with fields: [list fields]"* |
| State Management | *"Create a Redux slice / Zustand store for managing [feature] state"* |
| Form with Validation | *"Create a form component with validation for [describe form fields]"* |

### B. Working with Existing Code

| Task | How |
|------|-----|
| Understand code | Select code → *"Explain this code"* |
| Refactor | Select code → *"Refactor this to be more readable and performant"* |
| Fix bug | Paste error → *"Fix this error: [paste error]"* |
| Add feature to existing | *"Add pagination to this existing list component"* (with file open) |
| Optimize | *"Optimize this database query for performance"* |

### C. Using `@workspace` in Copilot Chat
```
@workspace How is authentication implemented in this project?
@workspace Where is the user API called?
@workspace Generate a new feature following the same patterns used in the codebase
```

---

## 5️⃣ TESTING (AI-Generated Tests)

### What You Can Do
| Action | Prompt |
|--------|--------|
| Unit Tests | *"Generate unit tests for this function using Jest"* |
| Integration Tests | *"Generate integration tests for this API endpoint"* |
| E2E Tests | *"Generate Cypress/Playwright E2E tests for the login flow"* |
| Test Data | *"Generate test fixtures for this component"* |
| Edge Cases | *"What edge cases should I test for this function?"* |

### 💡 Pro Tip
> After writing any code, immediately ask: *"Generate comprehensive tests for the code I just wrote"*

---

## 6️⃣ CODE REVIEW & QUALITY (AI-Assisted)

| Action | How |
|--------|-----|
| PR Description | *"Write a PR description for these changes: [paste diff]"* |
| Code Review | *"Review this code for bugs, security issues, and best practices"* |
| Documentation | *"Generate JSDoc comments for all functions in this file"* |
| README | *"Generate a README for this project"* |

---

## 📋 Team Training Plan

### Week 1: Foundations
- [ ] Everyone installs **GitHub Copilot** extension in VS Code
- [ ] Practice: Use Copilot autocomplete for daily coding
- [ ] Practice: Use Copilot Chat to explain existing code in the repo

### Week 2: Jira + AI
- [ ] Practice: Pick a Jira ticket → paste into AI → get technical breakdown
- [ ] Practice: Generate sub-tasks and acceptance criteria using AI
- [ ] Practice: Write technical approach docs with AI

### Week 3: Figma + API Docs + AI
- [ ] Practice: Screenshot Figma design → generate component code
- [ ] Practice: Paste API docs → generate service layer + types
- [ ] Practice: Generate mock data from API schemas

### Week 4: Full Feature with AI
- [ ] Each team member picks a Jira story
- [ ] Complete the ENTIRE feature using AI:
  - Jira breakdown → Figma to code → API integration → Tests
- [ ] Track: % of code written by AI vs manual
- [ ] Retrospective: What worked, what didn't

---

## ⚡ Quick Reference: Daily AI Shortcuts

| Keyboard Shortcut (VS Code) | Action |
|------------------------------|--------|
| `Tab` | Accept Copilot suggestion |
| `Esc` | Dismiss suggestion |
| `Cmd+Shift+I` (Mac) | Open Copilot Chat |
| `Cmd+I` (Mac) | Inline Copilot Edit |
| `Ctrl+Shift+I` (Windows) | Open Copilot Chat |
| `Ctrl+I` (Windows) | Inline Copilot Edit |

---

## 🎯 Success Metrics to Track

| Metric | How to Measure |
|--------|----------------|
| AI Code Adoption | % of PRs with AI-generated code |
| Development Speed | Story points delivered per sprint (before vs after) |
| Code Quality | Bug count, test coverage |
| Team Satisfaction | Survey: "How helpful is AI in your workflow?" |
| Time Saved | Hours saved per feature (estimate) |

---

## ⚠️ Important Guidelines for the Team

### DO ✅
- Always **review AI-generated code** before committing
- Provide **maximum context** (Jira ticket, API docs, existing patterns)
- Use AI for **repetitive/boilerplate** code (forms, CRUD, tests)
- **Iterate** with AI — refine the output in multiple steps
- Use `@workspace` to help AI understand your project patterns

### DON'T ❌
- Don't blindly commit AI code without review
- Don't share sensitive credentials/secrets with AI
- Don't skip understanding — if you don't understand the code, ask AI to explain it
- Don't use AI-generated code for security-critical logic without expert review

---

## 🔗 Recommended AI Tools Stack

| Tool | Purpose | Access |
|------|---------|--------|
| **GitHub Copilot** | Code completion + Chat in VS Code | Extension |
| **GitHub Copilot Chat** | Complex code generation, Q&A | Built into Copilot |
| **Copilot Agent Mode** | Multi-file edits, full features | VS Code Copilot |
| **Cursor** (alternative) | AI-first code editor | cursor.sh |

---

*Created: April 2026 | Review Monthly | Adapt Based on Team Feedback*
