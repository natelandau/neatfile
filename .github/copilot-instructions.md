# Coding Standards and Guidelines

## Git workflow rules

- ALWAYS work in a feature branch. Never commit directly to main.
- NEVER merge to main unless explicit permission is granted by the user.
- NEVER run `git push origin main` or `git merge main` without explicit permission.
- Create descriptive branch names: `feature/<name>`, `fix/<name>`, `refactor/<name>`
- When in doubt, ask before performing any operations that affect the main branch.

## Git commit message rules

- When you finish applying changes, the last line of the message should be "Don't forget to commit!" and give me a commit command as well.
- Always use angular style conventional commits style. No Exceptions!
- The first line of the commit should never be more than 50 characters
- Each commit message consists of a header, and a body. The header has a special format that includes a type, a scope and a subject: `(<scope>): <subject>`
- The types must be one of the following:
    - build: Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm)
    - ci: Changes to our CI configuration files and scripts (example scopes: Travis, Circle, BrowserStack, SauceLabs)
    - docs: Documentation only changes
    - feat: A new feature
    - fix: A bug fix
    - perf: A code change that improves performance
    - refactor: A code change that neither fixes a bug nor adds a feature
    - style: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
    - test: Adding missing tests or correcting existing tests
- The scope should be the name of the package, feature, codebase, or area that is effected
- The subject contains a succinct description of the change:
    - use the imperative, present tense: "change" not "changed" nor "changes" in the subject
    - don't capitalize the first letter of the subject
    - no dot (.) at the end of the subject
- In the body, just as in the summary, use the imperative, present tense: "fix" not "fixed" nor "fixes".
- The body will explain the motivation for the change in the commit message body. This commit message should explain WHY you are making the change. You can include a comparison of the previous behavior with the new behavior in order to illustrate the impact of the change.

### Commit Message Examples

- feat: add email notifications on new direct messages
- feat(shopping cart): add the amazing button
- feat(search): add global search to navbar
- feat!: remove ticket list endpoint
- fix(api): fix wrong calculation of request body checksum
- perf: decrease memory footprint by using HyperLogLog
- build: update dependencies
- refactor: implement fibonacci number calculation as recursion
- style: remove empty line
- docs(readme): update installation instructions
- docs: clarify the service limitation in providers.md guide
- fix(utils): ensure logging handles exceptions from `FastAPI`

## Global coding style and standards


- Only modify code directly relevant to the specific request. Avoid changing unrelated functionality.
- Break problems into smaller steps. Think through each step separately before implementing.
- Always provide a complete **PLAN** with **REASONING** based on evidence from code and logs before making changes.
- Explain your **OBSERVATIONS** clearly, then provide **REASONING** to identify the exact issue. Add console logs when needed to gather more information.
- In code, write comments ONLY in English.
- Make minimal changes to files - modify only what's necessary to complete the task. While ensuring the solution is complete, aim for the smallest possible number of line changes to maintain code clarity and minimize potential issues.
- Follow core software development principles:
    - TDD (Test-Driven Development): Write tests first, then implement the functionality
    - DRY (Don't Repeat Yourself): Avoid code duplication, extract reusable components
    - KISS (Keep It Simple, Stupid): Choose simple solutions over complex ones
    - SRP (single responsibility principle)
    - YAGNI (You Aren't Gonna Need It): Don't implement functionality until it's necessary
- Always write "clean code". Clean code requires adherence to specific principles. These principles help developers write code that is clear, concise, and, ultimately, a joy to work with.
- Choose names for variables, functions, and classes that reflect their purpose and behavior (e.g. `discount` would become `discount_price`, `price` would become `product_price`)
- Include or use auxiliary verbs in variable names when appropriate (e.g. `is_active`, `has_permission`)
- Use named constants instead of hard-coded values. Write constants with meaningful names that convey their purpose. (e.g. `discount = price * 0.1 # 10% discount` would become `TEN_PERCENT_DISCOUNT = 0.1
discount = price * TEN_PERCENT_DISCOUNT`)
- Follow the **single responsibility principle (SRP)**, which means that a function should have one purpose and perform it effectively.
- Follow the **DRY (Don't Repeat Yourself)** principle and avoid writing the same code more than once. Instead, reuse code using functions, classes, modules, libraries, or other abstractions
- Encapsulate nested conditionals into functions. Nested conditionals make code difficult to read and comprehend. You need to simplify the main code flow by encapsulating complex conditionals into well-named functions.
- Keep inline-comments minimal, but make them meaningful. Use comments only when necessary and make sure they add real value - typically only to clarify complex logic or unusual decisions or to explain the why
- Handle errors and edge cases at the beginning of functions
- Use early returns for errors conditions to avoid deeply nested if statements
- Use guard clauses to handle preconditions and invalid states early
- no extra code beyond what is absolutely necessary to solve the problem the user provides (i.e. no technical debt)

