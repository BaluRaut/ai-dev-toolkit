# 🔗 How to Connect Figma + Jira + API Docs with AI

> The practical, step-by-step guide — no theory, just "do this, then this".

---

## 🎯 The Big Picture: YOU Are the Connector

```
There is NO auto-plugin that connects all 3 to AI.
Instead, YOU copy context from each tool → paste into AI.

It takes 2-3 minutes and the results are 10x better.

┌──────────┐     COPY      ┌─────────────────┐     OUTPUT     ┌──────────┐
│  JIRA    │──────────────▶│                 │──────────────▶│ Working  │
│  Ticket  │   (text)      │                 │               │ Code     │
├──────────┤               │   AI AGENT      │               ├──────────┤
│  FIGMA   │──────────────▶│   (Copilot      │──────────────▶│ Tests    │
│  Design  │ (screenshot)  │    Agent Mode)  │               ├──────────┤
├──────────┤               │                 │──────────────▶│ Types    │
│  API     │──────────────▶│                 │               ├──────────┤
│  Docs    │   (text)      │                 │──────────────▶│ Services │
└──────────┘               └─────────────────┘               └──────────┘
```

---

## 📋 STEP-BY-STEP: Connecting All 3

---

### STEP 1: Grab Context from JIRA (2 min)

#### Option A: Simple Copy-Paste
```
1. Open your Jira ticket
2. Copy these fields:
   - Title
   - Description
   - Acceptance Criteria
   - Any comments with requirements
3. Paste into a text file or directly into AI prompt
```

#### Option B: Use Jira's "Export" 
```
1. Open Jira ticket
2. Click "..." menu → "Export as PDF" or "Print"
3. Copy all text from the export
```

#### Option C: Use Jira API (Advanced/Automated)
```bash
# Get ticket details via Jira REST API
curl -s -u your-email@company.com:YOUR_API_TOKEN \
  "https://your-company.atlassian.net/rest/api/3/issue/PROJ-123" \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Title: {data['fields']['summary']}\")
print(f\"Description: {data['fields']['description']}\")
print(f\"Status: {data['fields']['status']['name']}\")
print(f\"Priority: {data['fields']['priority']['name']}\")
"
```

#### What Your Jira Copy Should Look Like:
```markdown
JIRA TICKET: PROJ-123
Title: Implement User Profile Page
Description: Users should be able to view and edit their profile information
  including name, email, avatar, and notification preferences.

Acceptance Criteria:
- User can view their profile information
- User can edit name and email
- User can upload a profile avatar (max 5MB, jpg/png)
- User can toggle email notification preferences
- Changes are saved via API and show success toast
- Form validates email format
- Mobile responsive

Priority: High
Sprint: Sprint 14
```

---

### STEP 2: Grab Context from FIGMA (2 min)

#### Option A: Screenshot (Fastest & Most Common ⭐)
```
1. Open Figma → Navigate to the design frame
2. Select the frame/component you need to build
3. Take a screenshot:
   - Mac: Cmd+Shift+4 → drag to select
   - Or: Right-click frame → "Copy as PNG"
4. Paste screenshot directly into Copilot Chat (it supports images!)
```

#### Option B: Copy CSS from Figma Dev Mode
```
1. Open Figma → Switch to "Dev Mode" (toggle at top)
2. Click on any element
3. Right panel shows CSS properties
4. Click "Copy all CSS" for each element
5. Paste into AI for conversion to your framework
```

**Example copied CSS from Figma:**
```css
/* Profile Card - from Figma Dev Mode */
width: 400px;
height: auto;
padding: 24px;
background: #FFFFFF;
border-radius: 12px;
box-shadow: 0px 4px 16px rgba(0, 0, 0, 0.08);
font-family: 'Inter', sans-serif;

/* Avatar */
width: 80px;
height: 80px;
border-radius: 50%;

/* Name */
font-size: 24px;
font-weight: 600;
color: #1A1A2E;

/* Email */
font-size: 14px;
color: #6B7280;
```

#### Option C: Describe the Design in Text
```
If you can't screenshot, describe it:

"The profile page has:
- A card with white background, rounded corners, subtle shadow
- Profile avatar (80px circle) at top center
- User name below (24px, bold)
- Email below name (14px, gray)
- Edit button (blue, rounded)
- A form section with: Name input, Email input, Avatar upload area
- Save and Cancel buttons at bottom
- Mobile: single column, full width"
```

#### Option D: Figma Plugin → Code (Automated)
```
Plugins that export Figma to code directly:
1. Locofy.ai    → Exports to React/Next.js
2. Anima        → Exports to HTML/React/Vue
3. Builder.io   → Exports to any framework

Install in Figma → Select frame → Export → Get code → Refine with AI
```

---

### STEP 3: Grab Context from API DOCS (2 min)

#### Option A: Copy from Swagger/OpenAPI UI
```
1. Open your API documentation (Swagger UI, Postman, etc.)
2. Find the relevant endpoints
3. Copy:
   - URL + Method (GET /api/users/:id)
   - Request body example
   - Response body example
   - Headers required
   - Error responses
```

#### Option B: Copy from Postman
```
1. Open Postman → Find the API collection
2. Click on the endpoint
3. Copy the request URL + method
4. Click "Body" tab → Copy request body
5. Click "Response" section → Copy example response
6. OR: Export collection as JSON → feed to AI
```

#### Option C: Use Swagger JSON Directly
```
If you have a swagger.json or openapi.yaml file:
1. Download it
2. Drop it into your project root
3. Tell AI: "@workspace Read the swagger.json and generate services"
```

#### Option D: Copy from README/Wiki
```
If API docs are in a wiki or README:
1. Copy the endpoint documentation
2. Include request/response examples
```

#### What Your API Copy Should Look Like:
```markdown
API ENDPOINTS FOR USER PROFILE:

1. GET /api/users/:id
   Headers: Authorization: Bearer <token>
   Response 200:
   {
     "id": "user_123",
     "name": "John Doe",
     "email": "john@example.com",
     "avatar": "https://cdn.example.com/avatars/user_123.jpg",
     "notifications": {
       "email": true,
       "push": false
     },
     "createdAt": "2025-01-15T10:30:00Z"
   }

2. PUT /api/users/:id
   Headers: Authorization: Bearer <token>
   Request Body:
   {
     "name": "John Updated",
     "email": "john.new@example.com",
     "notifications": { "email": false, "push": true }
   }
   Response 200: { "message": "Profile updated", "user": { ...updated user } }
   Response 400: { "error": "Invalid email format" }
   Response 401: { "error": "Unauthorized" }

3. POST /api/users/:id/avatar
   Headers: Authorization: Bearer <token>
   Content-Type: multipart/form-data
   Body: file (max 5MB, jpg/png only)
   Response 200: { "avatar": "https://cdn.example.com/avatars/new.jpg" }
   Response 413: { "error": "File too large" }
```

---

### STEP 4: Combine All 3 → Feed to AI Agent (THE MAGIC STEP ✨)

Now you have all 3 pieces. Here's exactly how to combine them:

#### Open VS Code → Copilot Agent Mode (Cmd+Shift+I)

```markdown
PASTE THIS SINGLE PROMPT:
─────────────────────────

## Context

### Jira Ticket (PROJ-123):
[PASTE YOUR JIRA TICKET TEXT HERE]

### Design Reference:
[PASTE FIGMA SCREENSHOT HERE — or describe the design]
[PASTE FIGMA CSS VALUES HERE — if you have them]

### API Endpoints:
[PASTE YOUR API ENDPOINT DOCS HERE]

### Existing Project Info:
- Tech Stack: React 18, TypeScript, Tailwind CSS, React Query, Zustand
- Project follows feature-based folder structure

## Task
Build the complete User Profile feature based on the Jira ticket above.
Match the Figma design exactly.
Connect to the API endpoints provided.
Follow existing patterns in @workspace.

Generate:
1. TypeScript types for API request/response
2. API service functions  
3. React Query hooks
4. React components matching the Figma design
5. Form validation (email format, file size)
6. Loading states and error handling
7. Unit tests
8. Mobile responsive
```

---

## 🎬 REAL EXAMPLE: Complete Walkthrough

Let me show you exactly what this looks like in practice:

### Your Jira Ticket:
```
PROJ-456: Build Product Listing Page
- Display products in a responsive grid
- Filter by category (dropdown)
- Search by product name
- Sort by: Price low-high, high-low, Newest
- Pagination (12 items per page)
- Click product card → go to detail page
```

### Your Figma Screenshot:
```
(You would paste a screenshot showing:)
- A header with search bar and filter dropdown
- A 3-column grid of product cards
- Each card has: image, title, price, rating, "Add to Cart" button
- Pagination at bottom
```

### Your API Docs:
```
GET /api/products?category=electronics&search=laptop&sort=price_asc&page=1&limit=12

Response:
{
  "products": [
    {
      "id": "prod_1",
      "name": "MacBook Pro 16",
      "price": 2499.99,
      "image": "https://cdn.example.com/products/macbook.jpg",
      "category": "electronics",
      "rating": 4.8,
      "reviewCount": 234
    }
  ],
  "pagination": {
    "total": 156,
    "page": 1,
    "limit": 12,
    "totalPages": 13
  }
}

GET /api/categories
Response: { "categories": ["electronics", "clothing", "books", "home"] }
```

### The Combined Prompt You Give to AI Agent:
```markdown
## Jira: PROJ-456 — Product Listing Page

Requirements:
- Display products in responsive grid (3 cols desktop, 2 tablet, 1 mobile)
- Filter by category dropdown
- Search by product name (debounced)
- Sort: Price low→high, high→low, Newest
- Pagination: 12 items/page
- Product card: image, title, price, rating stars, "Add to Cart"
- Click card → navigate to /products/:id

## Design: [PASTE SCREENSHOT]
- Clean white background
- Cards with subtle shadow and rounded corners
- Blue primary color (#3B82F6)
- Inter font family

## API:
GET /api/products?category=&search=&sort=price_asc&page=1&limit=12
Response: { products: [...], pagination: { total, page, limit, totalPages } }

GET /api/categories  
Response: { categories: ["electronics", "clothing", ...] }

## Project Stack: 
React 18 + TypeScript + Tailwind + React Query + React Router

## Generate:
1. Types in src/types/product.ts
2. API service in src/services/productService.ts
3. Hooks in src/hooks/useProducts.ts
4. Components: ProductGrid, ProductCard, FilterBar, SearchInput, Pagination
5. Page: src/pages/ProductListPage.tsx
6. Tests for all components
7. Follow existing patterns in @workspace
```

### What the AI Agent Does:
```
✅ Creates src/types/product.ts          (TypeScript interfaces)
✅ Creates src/services/productService.ts (Axios API calls)
✅ Creates src/hooks/useProducts.ts       (React Query hooks)
✅ Creates src/components/ProductCard.tsx  (Single product card)
✅ Creates src/components/ProductGrid.tsx  (Grid layout)
✅ Creates src/components/FilterBar.tsx    (Category + Sort dropdowns)
✅ Creates src/components/SearchInput.tsx  (Debounced search)
✅ Creates src/components/Pagination.tsx   (Page navigation)
✅ Creates src/pages/ProductListPage.tsx   (Full page composition)
✅ Updates src/routes.tsx                  (Adds new route)
✅ Creates src/__tests__/ProductCard.test.tsx
✅ Creates src/__tests__/useProducts.test.ts
✅ Runs npm start → checks for errors → fixes if any
```

---

## 🔄 WORKFLOW TEMPLATE (Copy This for Every Feature)

Save this template — use it for every new feature:

```markdown
# AI Agent Prompt Template

## 📋 JIRA TICKET
Ticket: [TICKET-ID]
Title: [Title]
Description: [Paste description]
Acceptance Criteria:
- [AC 1]
- [AC 2]
- [AC 3]

## 🎨 FIGMA DESIGN
[Paste screenshot OR describe the design]
Design notes:
- Colors: [primary color, secondary, etc.]
- Font: [font family]
- Layout: [describe layout]
- Key interactions: [hover effects, animations, etc.]

## 🔌 API ENDPOINTS
[Paste all relevant endpoint docs with request/response examples]

## ⚙️ PROJECT CONTEXT
- Tech Stack: [React/Angular/Vue + other libs]
- Folder Structure: [feature-based / module-based]
- State Management: [Redux/Zustand/Context]
- Styling: [Tailwind/CSS Modules/Styled Components]
- Testing: [Jest/Vitest + RTL/Enzyme]

## ✅ GENERATE
1. TypeScript types/interfaces
2. API service layer
3. Data fetching hooks
4. UI components (match Figma exactly)
5. Page composition
6. Route integration
7. Form validation
8. Error handling + loading states
9. Unit tests
10. Follow existing patterns in @workspace
```

---

## ⚡ QUICK REFERENCE: Copy Methods

| Source | How to Copy | What to Copy |
|--------|------------|--------------|
| **Jira** | Select text → Cmd+C | Title, Description, ACs, Comments |
| **Jira (API)** | `curl` command | JSON response → paste into AI |
| **Figma** | Cmd+Shift+4 (screenshot) | The specific frame/screen |
| **Figma CSS** | Dev Mode → Click element → Copy | CSS properties of each element |
| **Figma (Plugin)** | Locofy/Anima export | Generated React code |
| **Swagger UI** | Copy from browser | Endpoint URL, Request, Response |
| **Postman** | Copy from collection | Request + Response examples |
| **Postman (Export)** | Export as JSON | Full collection file |
| **API Wiki** | Copy from docs page | Endpoint documentation |
| **swagger.json** | Drop file in project | AI reads it with @workspace |

---

## 🤖 AUTOMATION: Make It Even Faster

### Create a Script to Fetch Jira + API Docs Automatically

```bash
#!/bin/bash
# save as: fetch-context.sh

JIRA_TICKET=$1  # e.g., PROJ-123
JIRA_BASE="https://your-company.atlassian.net"
JIRA_EMAIL="your-email@company.com"
JIRA_TOKEN="your-api-token"

echo "========================================="
echo "📋 JIRA TICKET: $JIRA_TICKET"
echo "========================================="

# Fetch Jira ticket
curl -s -u "$JIRA_EMAIL:$JIRA_TOKEN" \
  "$JIRA_BASE/rest/api/3/issue/$JIRA_TICKET" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
fields = data['fields']
print(f\"Title: {fields['summary']}\")
print(f\"Type: {fields['issuetype']['name']}\")
print(f\"Priority: {fields['priority']['name']}\")
print(f\"Description: {fields.get('description', 'N/A')}\")
"

echo ""
echo "========================================="
echo "🔌 API DOCS (from Swagger)"
echo "========================================="

# If you have a swagger endpoint, fetch relevant paths
# Customize the URL to your API docs
curl -s "https://your-api.com/swagger.json" | \
  python3 -c "
import json, sys
data = json.load(sys.stdin)
for path, methods in data.get('paths', {}).items():
    for method, details in methods.items():
        print(f\"{method.upper()} {path}\")
        print(f\"  Summary: {details.get('summary', 'N/A')}\")
"
```

**Usage:**
```bash
chmod +x fetch-context.sh
./fetch-context.sh PROJ-123
# Copy the output → paste into AI agent prompt
```

### Save Your Swagger/OpenAPI in the Repo
```
project/
├── docs/
│   ├── swagger.json        ← Drop your API spec here
│   └── api-examples.md     ← Paste example responses here
├── src/
│   └── ...
```

Then in Copilot Agent Mode:
```
"@workspace Read docs/swagger.json and build the service layer 
for all user-related endpoints"
```

---

## ⏱️ THE COMPLETE 5-MINUTE WORKFLOW

```
MINUTE 1: 📋 Copy Jira ticket text → paste into prompt
MINUTE 2: 🎨 Screenshot Figma design → paste into prompt  
MINUTE 3: 🔌 Copy API endpoint docs → paste into prompt
MINUTE 4: ⚙️ Add project context + what to generate
MINUTE 5: 🚀 Hit Enter → Agent builds everything

Then: ☕ Review the output while sipping coffee
```

---

*This is the practical "how" — no plugins needed, just copy-paste + AI agent = done.*
