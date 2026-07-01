# Architect Breakdown Rubric

Evaluate the task breakdown produced by the architect agent.

## Required Elements

- tasks list with at least one backend and one frontend task
- rationale explaining the decomposition
- FastAPI or endpoint mentioned for backend
- authentication or auth mentioned
- clear task titles

## Quality Criteria

- Each task has a clear, actionable title
- Rationale connects the story requirements to the decomposition
- Backend tasks reference the auth endpoint
- Frontend tasks reference the login form or UI component
- No ambiguous or duplicate tasks

## Anti-Patterns (penalize)

- Missing rationale
- Tasks without titles
- No reference to authentication
- Mixing frontend and backend concerns in one task without justification
