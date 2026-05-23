# Poll Post Feature — Implementation Spec

## Overview
Add a "Poll Post" feature to Easy Social. Users can create posts with 2–4 voting options. Other users can vote on one option, and the system displays real-time vote percentages.

---

## Database Schema (Supabase / PostgreSQL)

### Table: `polls`
Linked 1-to-1 with the existing `posts` table.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | uuid | PRIMARY KEY, default gen_random_uuid() | |
| post_id | uuid | NOT NULL, FOREIGN KEY → posts(id) ON DELETE CASCADE | |
| created_at | timestamptz | default now() | |

### Table: `poll_options`
Each poll has 2–4 options.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | uuid | PRIMARY KEY, default gen_random_uuid() | |
| poll_id | uuid | NOT NULL, FOREIGN KEY → polls(id) ON DELETE CASCADE | |
| text | varchar(100) | NOT NULL | Option label |
| order | int | NOT NULL | Display order (1–4) |

### Table: `poll_votes`
One vote per user per poll (enforced by unique constraint).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | uuid | PRIMARY KEY, default gen_random_uuid() | |
| poll_id | uuid | NOT NULL, FOREIGN KEY → polls(id) ON DELETE CASCADE | |
| option_id | uuid | NOT NULL, FOREIGN KEY → poll_options(id) ON DELETE CASCADE | |
| user_id | uuid | NOT NULL, FOREIGN KEY → users(id) ON DELETE CASCADE | |
| created_at | timestamptz | default now() | |

**Unique constraint:** `(poll_id, user_id)` — one vote per user per poll.

### Relationships
```
posts (1) ──── (1) polls (1) ──── (N) poll_options
                        │
                        └────── (N) poll_votes ──── (1) users
                                        │
                                        └──── (1) poll_options
```

---

## API Endpoints (Flask)

### POST `/api/posts`
Extend the existing post creation endpoint to support poll posts.

Request body:
```json
{
  "content": "What's your favourite stack?",
  "poll": {
    "options": ["Flask", "Django", "FastAPI", "Express"]
  }
}
```
- `poll` is optional. If present, create a poll linked to the post.
- Must have 2–4 options.
- Each option text max 100 characters.

Response: same as existing post creation, with poll data included.

---

### POST `/api/polls/<poll_id>/vote`
Cast a vote on a poll.

Request body:
```json
{
  "option_id": "<uuid>"
}
```

Rules:
- User must be authenticated.
- User cannot vote twice on the same poll (return 409 if already voted).
- `option_id` must belong to the given `poll_id` (return 400 if not).

Response:
```json
{
  "success": true,
  "results": [
    { "option_id": "...", "text": "Flask", "votes": 10, "percentage": 50.0 },
    { "option_id": "...", "text": "Django", "votes": 6, "percentage": 30.0 },
    { "option_id": "...", "text": "FastAPI", "votes": 4, "percentage": 20.0 }
  ]
}
```

---

### GET `/api/polls/<poll_id>/results`
Get current vote counts and percentages.

Response: same format as the vote response above, plus `user_voted_option_id` if the current user has already voted.

---

## Frontend

### Create Post Form
- Add a toggle "Add Poll" to the existing post creation form.
- When toggled on, show 2 option inputs by default.
- "Add option" button to add up to 4 options.
- "Remove" button on each option (minimum 2 must remain).
- Validate: all option fields must be filled before submitting.

### Post Display
- If a post has a poll, render the options as buttons.
- If the current user has not voted: show clickable option buttons.
- If the current user has voted: show a progress bar for each option with percentage and vote count.
- Update the UI immediately after voting (no page reload).

---

## Tests

### Unit Tests
- `test_verify_poll_options`: test that creating a poll with <2 or >4 options raises validation error.
- `test_vote_percentage_calculation`: test that vote percentages are calculated correctly.
- `test_duplicate_vote_rejected`: test that voting twice on the same poll returns 409.
- `test_invalid_option_rejected`: test that voting with an option_id not belonging to the poll returns 400.

### Integration Tests
- `test_create_poll_post`: POST to `/api/posts` with poll data, assert poll and options are created in DB.
- `test_cast_vote`: POST to `/api/polls/<id>/vote`, assert vote is recorded and results are returned.
- `test_duplicate_vote_integration`: vote twice as the same user, assert second vote returns 409.
- `test_get_results`: GET `/api/polls/<id>/results`, assert correct percentages returned.

### End-to-End Tests (Playwright)
- `test_e2e_create_poll`: log in, create a poll post with 3 options, assert it appears in the feed.
- `test_e2e_vote`: log in as a different user, vote on a poll, assert percentages update.
- `test_e2e_no_double_vote`: vote once, assert the options become non-clickable after voting.

---

## Notes
- All DB operations should use Supabase client.
- Use Supabase Row Level Security (RLS) to ensure users can only insert their own votes.
- The unique constraint on `(poll_id, user_id)` in `poll_votes` is the primary guard against double voting — enforce it at both the DB level and application level.