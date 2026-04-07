"""
Prompt Templates — Structured prompts for Claude agent.
"""


def build_full_feature_prompt(
    jira_context: str,
    figma_context: str,
    api_context: str,
    tech_stack: str,
    extra_instructions: str = "",
) -> str:
    """
    Build the master prompt that combines Jira + Figma + API docs.
    This is what gets sent to Claude.
    """
    prompt = f"""You are a senior full-stack developer. Your task is to generate production-ready code for a feature based on the context provided below.

## IMPORTANT RULES:
1. Generate COMPLETE, working code — no placeholders, no TODOs, no "// implement here"
2. Follow the tech stack and patterns specified
3. Include TypeScript types/interfaces
4. Include proper error handling
5. Include loading states
6. Make it responsive (mobile-first)
7. Follow accessibility best practices
8. Generate unit tests

## OUTPUT FORMAT:
For EACH file you generate, use this exact format:

===FILE: path/to/file.ts===
```typescript
// file contents here
```
===END FILE===

Generate ALL files needed for a complete, working feature.

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
4. **Components** — React components matching the design
5. **Page/Container** — Main page component that composes everything
6. **Tests** — Unit tests for services, hooks, and components
7. **Styles** — Any additional styles needed (if using CSS modules)

{extra_instructions}

Now generate ALL the code files:"""

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
