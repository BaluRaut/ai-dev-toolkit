"""
Prompt Templates — Structured prompts for Claude agent.

Includes templates for:
  - Full feature generation (with unit tests + Playwright E2E)
  - Standalone unit test generation
  - Standalone Playwright E2E test generation
  - Code review, refactoring, bug fixing
"""


def build_full_feature_prompt(
    jira_context: str,
    figma_context: str,
    api_context: str,
    tech_stack: str,
    extra_instructions: str = "",
    include_unit_tests: bool = True,
    include_e2e_tests: bool = True,
) -> str:
    """
    Build the master prompt that combines Jira + Figma + API docs.
    Now automatically includes unit tests AND Playwright E2E tests.
    """

    # Build the testing section dynamically
    test_instructions = ""
    test_files = ""

    if include_unit_tests:
        test_instructions += """
## 🧪 UNIT TEST REQUIREMENTS:
- Use **Jest** + **React Testing Library** (or Vitest if project uses it)
- Write tests for EVERY component, hook, service, and utility
- Test happy path, error states, edge cases, and loading states
- Mock all API calls using `msw` (Mock Service Worker) or jest.mock
- Mock React Router navigation
- Achieve **>80% code coverage**
- Use descriptive test names: `should [behavior] when [condition]`
- Group with `describe` blocks per component/function
- Test user interactions: clicks, form inputs, submissions
- Test accessibility: roles, labels, keyboard navigation
"""
        test_files += """
8. **Unit Tests** — Jest + RTL tests for every component
   - `src/__tests__/[ComponentName].test.tsx` — render, interactions, states
   - `src/__tests__/[hookName].test.ts` — hook behavior, API mocking
   - `src/__tests__/[serviceName].test.ts` — API calls, error handling
   - `src/__tests__/setup.ts` — test setup with MSW handlers
   - `src/__mocks__/handlers.ts` — MSW request handlers for mock API
"""

    if include_e2e_tests:
        test_instructions += """
## 🎭 PLAYWRIGHT E2E TEST REQUIREMENTS:
- Use **Playwright** (@playwright/test)
- Write end-to-end tests that simulate REAL user flows
- Test the COMPLETE user journey (navigate → interact → verify)
- Use `page.goto()`, `page.click()`, `page.fill()`, `expect(page)` etc.
- Use **Page Object Model** pattern for reusable selectors
- Add `data-testid` attributes to components for reliable selectors
- Test on multiple viewports: desktop (1280x720) and mobile (375x667)
- Test: page load, navigation, form submission, error states, success states
- Include proper `beforeEach` / `afterEach` setup
- Add meaningful assertions with `expect(locator).toBeVisible()`, `.toHaveText()`, etc.
- Handle async operations with `waitForResponse` or `waitForSelector`
"""
        test_files += """
9. **Playwright E2E Tests** — Full user flow tests
   - `e2e/[featureName].spec.ts` — Complete user journey test
   - `e2e/pages/[PageName]Page.ts` — Page Object Model for selectors
   - `e2e/fixtures/test-data.ts` — Test data and constants
   - `playwright.config.ts` — Playwright config (baseURL, browsers, viewport)
"""

    prompt = f"""You are a senior full-stack developer AND testing expert. Your task is to generate production-ready code WITH comprehensive tests for a feature based on the context provided below.

## IMPORTANT RULES:
1. Generate COMPLETE, working code — no placeholders, no TODOs, no "// implement here"
2. Follow the tech stack and patterns specified
3. Include TypeScript types/interfaces
4. Include proper error handling
5. Include loading states
6. Make it responsive (mobile-first)
7. Follow accessibility best practices
8. Add `data-testid` attributes to ALL interactive elements for testing
9. Generate COMPLETE unit tests (Jest + RTL)
10. Generate COMPLETE Playwright E2E tests

## OUTPUT FORMAT:
For EACH file you generate, use this exact format:

===FILE: path/to/file.ts===
```typescript
// file contents here
```
===END FILE===

Generate ALL files needed for a complete, working, TESTED feature.
{test_instructions}
---

# CONTEXT

{jira_context}

---

{figma_context}

---

{api_context}

---

## ⚙️ TECH STACK & PROJECT INFO
{tech_stack}

---

## ✅ FILES TO GENERATE:
1. **Types/Interfaces** — TypeScript types for API request/response
2. **API Service** — Functions to call each API endpoint with error handling
3. **Custom Hooks** — React hooks for data fetching (React Query or SWR)
4. **Components** — React components matching the design (with data-testid attributes!)
5. **Page/Container** — Main page component that composes everything
6. **Route Integration** — Add route to router
7. **Styles** — Any additional styles needed
{test_files}
{extra_instructions}

Now generate ALL the code files INCLUDING all unit tests and E2E tests:"""

    return prompt


def build_code_review_prompt(code: str) -> str:
    """Build a prompt for code review."""
    return f"""You are a senior code reviewer. Review the following code for:

1. **Bugs & Logic Errors** — Find any bugs or incorrect logic
2. **Security** — XSS, injection, auth issues, exposed secrets
3. **Performance** — N+1 queries, unnecessary re-renders, memory leaks
4. **Best Practices** — Code style, naming, DRY, SOLID principles
5. **Error Handling** — Missing try/catch, unhandled edge cases
6. **TypeScript** — Type safety issues, any usage, missing types
7. **Accessibility** — Missing ARIA, keyboard nav, screen reader issues

For each issue found, provide:
- Severity: 🔴 Critical | 🟡 Warning | 🔵 Suggestion
- File & line reference
- Description of the issue
- Suggested fix with code

## CODE TO REVIEW:
{code}
"""


def build_test_generation_prompt(code: str, framework: str = "Jest + React Testing Library") -> str:
    """Build a prompt for test generation."""
    return f"""You are a testing expert. Generate comprehensive tests for the code below.

## TESTING RULES:
1. Use {framework}
2. Test happy paths AND edge cases
3. Test error states
4. Mock external dependencies (API calls, etc.)
5. Achieve >80% code coverage
6. Use descriptive test names: "should [expected behavior] when [condition]"
7. Group tests with describe blocks

## OUTPUT FORMAT:
For EACH test file, use:

===FILE: path/to/__tests__/filename.test.ts===
```typescript
// test contents
```
===END FILE===

## CODE TO TEST:
{code}

Generate all test files now:"""


def build_refactor_prompt(code: str, instructions: str = "") -> str:
    """Build a prompt for code refactoring."""
    return f"""You are a refactoring expert. Refactor the following code while maintaining ALL existing functionality.

## REFACTORING GOALS:
1. Improve readability and maintainability
2. Remove code duplication (DRY)
3. Apply SOLID principles
4. Improve TypeScript types (remove 'any')
5. Extract reusable utilities
6. Improve naming
7. Add JSDoc comments to public functions

{f"## SPECIFIC INSTRUCTIONS: {instructions}" if instructions else ""}

## OUTPUT FORMAT:
For EACH refactored file, use:

===FILE: path/to/file.ts===
```typescript
// refactored contents
```
===END FILE===

## CODE TO REFACTOR:
{code}

Generate all refactored files:"""


def build_bug_fix_prompt(error_message: str, code: str) -> str:
    """Build a prompt for debugging and fixing."""
    return f"""You are a debugging expert. Find the root cause and fix the bug.

## ERROR:
```
{error_message}
```

## RELEVANT CODE:
{code}

## YOUR TASK:
1. **Root Cause** — Explain why this error is happening
2. **Fix** — Provide the corrected code
3. **Prevention** — Suggest how to prevent this in the future

## OUTPUT FORMAT:
### Root Cause
[explanation]

### Fix
===FILE: path/to/file.ts===
```typescript
// fixed code
```
===END FILE===

### Prevention
[suggestions]
"""


def build_playwright_e2e_prompt(
    code: str,
    feature_description: str = "",
    base_url: str = "http://localhost:3000",
) -> str:
    """Build a prompt specifically for Playwright E2E test generation."""
    return f"""You are a senior QA automation engineer specializing in Playwright E2E testing.
Generate comprehensive end-to-end tests for the feature described below.

## PLAYWRIGHT E2E TESTING RULES:

### Structure:
- Use **@playwright/test** (import {{ test, expect }} from '@playwright/test')
- Use **Page Object Model** pattern — one class per page/component
- Put page objects in `e2e/pages/` folder
- Put specs in `e2e/` folder
- Put test data in `e2e/fixtures/`
- Generate `playwright.config.ts` with proper settings

### Test Coverage — MUST include:
1. **Navigation** — Page loads correctly, URL is correct
2. **Rendering** — All key elements are visible on the page
3. **User Interactions** — Click buttons, fill forms, select dropdowns
4. **Form Validation** — Submit empty form, invalid data, valid data
5. **API Integration** — Wait for API calls, verify data displays
6. **Error States** — Network error, 404, 500 responses
7. **Loading States** — Skeleton/spinner shows during loading
8. **Success Flows** — Complete happy path end-to-end
9. **Responsive** — Test on desktop (1280x720) AND mobile (375x667)
10. **Accessibility** — Tab navigation, ARIA labels, focus management

### Best Practices:
- Use `data-testid` selectors (most reliable): `page.getByTestId('submit-btn')`
- Use role selectors: `page.getByRole('button', {{ name: 'Submit' }})`
- Use text selectors: `page.getByText('Welcome')`
- Always `await` async operations
- Use `page.waitForResponse()` for API call assertions
- Use `test.describe()` to group related tests
- Use `test.beforeEach()` for common setup (navigation)
- Take screenshots on failure: `await page.screenshot()`
- Add meaningful error messages to assertions

### Example Pattern:
```typescript
import {{ test, expect }} from '@playwright/test';
import {{ FeaturePage }} from './pages/FeaturePage';

test.describe('Feature Name', () => {{
  let featurePage: FeaturePage;

  test.beforeEach(async ({{ page }}) => {{
    featurePage = new FeaturePage(page);
    await featurePage.goto();
  }});

  test('should load page with all elements visible', async ({{ page }}) => {{
    await expect(featurePage.heading).toBeVisible();
    await expect(featurePage.submitButton).toBeVisible();
  }});

  test('should submit form successfully', async ({{ page }}) => {{
    await featurePage.fillForm({{ name: 'John', email: 'john@test.com' }});
    await featurePage.submit();
    await expect(featurePage.successMessage).toBeVisible();
  }});

  test('should show validation error for empty form', async ({{ page }}) => {{
    await featurePage.submit();
    await expect(featurePage.errorMessage).toBeVisible();
  }});
}});
```

### Page Object Model Pattern:
```typescript
import {{ type Page, type Locator }} from '@playwright/test';

export class FeaturePage {{
  readonly page: Page;
  readonly heading: Locator;
  readonly submitButton: Locator;

  constructor(page: Page) {{
    this.page = page;
    this.heading = page.getByTestId('feature-heading');
    this.submitButton = page.getByRole('button', {{ name: 'Submit' }});
  }}

  async goto() {{
    await this.page.goto('/feature');
  }}

  async fillForm(data: {{ name: string; email: string }}) {{
    await this.page.getByTestId('name-input').fill(data.name);
    await this.page.getByTestId('email-input').fill(data.email);
  }}

  async submit() {{
    await this.submitButton.click();
  }}
}}
```

## OUTPUT FORMAT:
For EACH file, use:

===FILE: path/to/file.ts===
```typescript
// file contents
```
===END FILE===

## FEATURE DESCRIPTION:
{feature_description if feature_description else "(Infer from the code below)"}

## BASE URL: {base_url}

## SOURCE CODE TO GENERATE E2E TESTS FOR:
{code}

Generate ALL E2E test files now (playwright.config.ts + page objects + specs + fixtures):"""


def build_unit_test_prompt(
    code: str,
    framework: str = "Jest + React Testing Library",
    include_msw: bool = True,
) -> str:
    """Build a prompt specifically for comprehensive unit test generation."""
    msw_section = """
### MSW (Mock Service Worker) Setup:
- Create MSW handlers for ALL API endpoints in the code
- Use `setupServer()` for Node.js test environment
- Mock success responses, error responses, slow responses
- Pattern:
```typescript
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';

const handlers = [
  http.get('/api/users', () => {
    return HttpResponse.json({ users: mockUsers });
  }),
  http.get('/api/users/:id', ({ params }) => {
    return HttpResponse.json(mockUsers.find(u => u.id === params.id));
  }),
];

const server = setupServer(...handlers);
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```
""" if include_msw else ""

    return f"""You are a senior testing engineer. Generate comprehensive unit tests for the code below.

## UNIT TESTING RULES:

### Framework: {framework}

### Test Structure:
- One test file per source file: `__tests__/[filename].test.ts(x)`
- Test setup file: `__tests__/setup.ts`
- Mock handlers: `__mocks__/handlers.ts`
- Use `describe()` blocks to group by function/component
- Use `it()` or `test()` with descriptive names
- Pattern: `"should [expected behavior] when [condition]"`

### What to Test for EACH file type:

**Components (.tsx):**
- ✅ Renders without crashing
- ✅ Displays correct initial content
- ✅ Handles user clicks / interactions
- ✅ Form inputs update correctly
- ✅ Form validation errors show
- ✅ Loading state renders skeleton/spinner
- ✅ Error state renders error message
- ✅ Empty state renders placeholder
- ✅ Conditional rendering works
- ✅ Props are passed correctly to children
- ✅ Accessibility: roles, labels, tab order

**Hooks (.ts):**
- ✅ Returns correct initial state
- ✅ Updates state on action
- ✅ Handles API success
- ✅ Handles API error
- ✅ Loading flag toggles correctly
- ✅ Refetch/retry works
- ✅ Cleanup on unmount

**Services (.ts):**
- ✅ Calls correct URL with correct method
- ✅ Sends correct request body / headers
- ✅ Returns parsed response data
- ✅ Handles 400 error
- ✅ Handles 401 (unauthorized)
- ✅ Handles 500 error
- ✅ Handles network timeout
- ✅ Handles malformed response

**Utilities (.ts):**
- ✅ Returns correct output for valid input
- ✅ Handles edge cases (null, undefined, empty)
- ✅ Handles boundary values
- ✅ Throws for invalid input
{msw_section}
### Best Practices:
- Use `screen.getByRole()`, `screen.getByTestId()`, `screen.getByText()`
- Use `userEvent` over `fireEvent` for realistic interactions
- Use `waitFor()` for async assertions
- Use `renderHook()` from `@testing-library/react-hooks` for hooks
- Mock `useRouter`, `useNavigate` etc. for navigation tests
- Use `jest.useFakeTimers()` for debounce/timeout tests
- Assert both positive AND negative: what SHOULD show AND what should NOT

### Coverage Target: >80%

## OUTPUT FORMAT:
For EACH test file, use:

===FILE: path/to/file.test.ts===
```typescript
// test contents
```
===END FILE===

## SOURCE CODE TO TEST:
{code}

Generate ALL unit test files with comprehensive coverage:"""
