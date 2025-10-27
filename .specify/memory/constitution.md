<!--
  Sync Impact Report
  ==================
  Version Change: N/A → 1.0.0
  Rationale: Initial constitution creation with three core principles

  Principles Added:
  - Documentation & Code Clarity
  - Smart Architecture & Design
  - Pragmatic Testing (80/20 Rule)

  Templates Updated:
  ✅ plan-template.md - Constitution Check section references this file
  ✅ spec-template.md - Aligns with documentation and testing standards
  ✅ tasks-template.md - Reflects testing discipline and documentation tasks

  Follow-up TODOs: None - all placeholders filled
-->

# Project Constitution

**Version**: 1.0.0
**Ratification Date**: 2025-10-24
**Last Amended**: 2025-10-24

## Preamble

This constitution establishes the foundational principles for all software development
within this project. These principles prioritize pragmatic engineering over dogma,
clarity over complexity, and value delivery over perfection.

## Core Principles

### Principle 1: Documentation & Code Clarity

**Name**: Clear Communication Through Code and Comments

**Rules**:

- Code comments MUST provide context, reasoning, and "why" rather than restating
  "what" the code does. Example: Instead of `// Set user active`, write
  `// Mark user active to prevent account cleanup job from archiving this record`

- All public APIs, functions, and modules MUST have documentation that explains:
  - Purpose and responsibility
  - Key assumptions and constraints
  - Non-obvious behavior or side effects
  - Examples of correct usage when behavior is not self-evident

- Complex algorithms or business logic MUST include comments explaining:
  - The problem being solved
  - Why this approach was chosen
  - Important edge cases or gotchas

- Documentation MUST be maintained alongside code changes. Outdated documentation
  is worse than no documentation.

- Self-documenting code is preferred, but NOT a substitute for explaining complex
  reasoning or non-obvious design decisions.

**Rationale**:

Code is read far more often than it is written. Future maintainers (including your
future self) need to understand not just what the code does, but why it exists and
what constraints shaped its design. Comments that add context and reasoning prevent
costly misunderstandings and enable confident refactoring.

**Examples**:

Good comment:
```
// Use binary search instead of linear scan because user lists can exceed 10k
// items during peak hours. Benchmark: O(log n) vs O(n) saves ~50ms at p95.
```

Bad comment:
```
// Loop through users
```

### Principle 2: Smart Architecture & Design

**Name**: Pragmatic Design Over Pattern Orthodoxy

**Rules**:

- Design decisions MUST be justified by actual project needs, not theoretical
  future requirements or pattern purity.

- Architecture MUST optimize for:
  - Simplicity: Fewest moving parts to achieve the goal
  - Clarity: Easy to understand and reason about
  - Evolvability: Can adapt as requirements change
  - Locality: Related code lives together

- Design patterns are tools, not mandates. Apply them when they solve a real
  problem you have today, not because they "might be useful later."

- Premature abstraction is prohibited. Wait until you have 2-3 concrete use cases
  before creating abstractions. Duplication is cheaper than the wrong abstraction.

- When choosing between two approaches:
  1. Prefer the simpler one unless complexity is clearly justified
  2. Document why the complex approach is necessary
  3. Consider whether you're solving a real problem or an imagined one

- Avoid over-engineering:
  - No layers without clear purpose
  - No frameworks when libraries suffice
  - No microservices when a monolith works
  - No database when files work

- YAGNI (You Aren't Gonna Need It) is the default. The burden of proof lies
  with complexity.

**Rationale**:

Software architecture serves the product and the team, not vice versa. Excessive
abstraction, premature optimization, and pattern-for-pattern's-sake create
maintenance burdens, cognitive overhead, and slower development velocity. Smart
design means choosing the right tool for the actual job at hand, and having the
discipline to keep things simple until complexity is truly warranted.

**Gates**:

Before adding architectural complexity (new layer, pattern, service, etc.), answer:
- What concrete problem does this solve today?
- What is the cost of NOT doing this right now?
- Can we solve this with simpler means?
- Have we tried the simple approach and found it lacking?

If you can't answer these clearly, defer the complexity.

### Principle 3: Pragmatic Testing (80/20 Rule)

**Name**: High-Value Testing Over Exhaustive Coverage

**Rules**:

- Testing MUST focus on delivering maximum confidence with minimum effort.
  The goal is NOT 100% coverage; the goal is confidence that the system works.

- Prioritize tests in this order:
  1. **Contract/Integration tests**: Test critical user journeys and API contracts.
     These provide the highest ROI by catching real user-facing issues.
  2. **Core business logic**: Test algorithms, calculations, validation rules,
     state machines - anything where bugs have high impact.
  3. **Unit tests**: Only for complex pure functions or isolated logic where
     integration tests would be inefficient.

- AVOID testing:
  - Trivial getters/setters or property access
  - Framework code or third-party libraries

- Each test MUST have clear value:
  - What user scenario or business requirement does it protect?
  - What specific bug class does it prevent?
  - Is this test the simplest way to catch this failure?

- Tests MUST be maintainable:
  - Clear, descriptive names that explain what is being tested
  - Minimal setup/teardown complexity
  - No brittle assertions on implementation details
  - Fast enough to run frequently (integration tests < 10s, unit tests < 1s)

- When deciding whether to write a test, ask:
  - "If this breaks, will we notice through other tests or obvious runtime failure?"
  - "Does this test catch bugs that matter to users?"
  - "Is this test's maintenance cost worth its bug-catching value?"

**Rationale**:

Testing has diminishing returns. The first 80% of value comes from 20% of possible
tests - those covering critical paths, complex logic, and user-facing contracts.
Chasing 100% coverage creates a maintenance burden that slows development without
proportional quality gains. Smart testing means investing effort where bugs are
most likely and most costly, not where coverage metrics demand it.

**Anti-Patterns to Avoid**:

- Writing tests just to hit coverage targets
- Testing every possible input combination when edge cases are obvious
- Recreating production code logic in test assertions
- Brittle tests that break when refactoring internals
- Slow test suites that discourage frequent running

**What Good Testing Looks Like**:

- You can refactor implementation details without breaking tests
- Tests fail clearly when user-facing behavior breaks
- Test suite runs fast enough to run on every commit
- New developers can understand what tests protect against
- Tests document expected behavior better than comments

## Governance

### Amendment Procedure

1. Proposed changes MUST be documented with:
   - Rationale for the change
   - Impact on existing code and practices
   - Migration path if breaking existing conventions

2. Constitution changes require:
   - Review by project maintainers
   - Update to version number (semantic versioning)
   - Sync check across all dependent templates

3. Version Bumping Rules:
   - **MAJOR**: Backward incompatible changes, principle removal, or redefinition
   - **MINOR**: New principle added or material expansion of existing guidance
   - **PATCH**: Clarifications, wording improvements, typo fixes

### Versioning Policy

This constitution follows semantic versioning (MAJOR.MINOR.PATCH):

- Version changes MUST be documented in the Sync Impact Report
- Each version MUST update LAST_AMENDED_DATE to date of change
- RATIFICATION_DATE remains constant (date of v1.0.0)

### Compliance Review

- All feature specifications MUST reference this constitution
- Implementation plans MUST include Constitution Check gate (see plan-template.md)
- Code reviews SHOULD verify adherence to these principles
- Deviations MUST be documented with justification in implementation plan

### Exceptions and Waivers

Principles may be waived for specific features when:

1. Clearly documented in the feature's plan.md under "Complexity Tracking"
2. Justification explains why the principle doesn't apply
3. Simpler alternatives are documented as insufficient
4. Impact is limited to the specific feature (no project-wide exceptions)

No blanket waivers. Each exception is case-by-case.

## Enforcement

These principles are enforced through:

- **Planning Phase**: Constitution Check gate in plan-template.md
- **Implementation Phase**: Code review against documented principles
- **Review Phase**: Cross-artifact consistency checks via `/speckit.analyze`

When principles conflict with delivery speed, document the tradeoff and revisit
post-delivery. Technical debt is acceptable when conscious and tracked.

## Interpretation

When applying these principles:

- Intent over letter: Understand the "why" behind each rule
- Context matters: Use judgment appropriate to project scale and maturity
- Question assumptions: If a principle seems wrong for your case, challenge it
  through the amendment process rather than ignoring it

This constitution serves the project. The project does not serve the constitution.

---

**End of Constitution v1.0.0**
