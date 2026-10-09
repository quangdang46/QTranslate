# Credentials handling

## Invariant: credentials are never persisted

Credentials supplied conversationally (e.g. a GitHub push token) are used
**transiently in a push URL only**:

```
git push "https://<token>@github.com/<owner>/<repo>.git" HEAD:main
```

They are never written to:

- `.git/config` (the remote stays `https://github.com/<owner>/<repo>.git`)
- any tracked file (verified with `git grep -l <token> HEAD -- .`)
- `.gitignore`d export/scratch files such as `context.txt`

## Push-time sanitization

Every push command pipes its output through
`sed -E 's/ghp_[A-Za-z0-9]+/***REDACTED***/g'` so the token is never echoed
back into the transcript.

## Export scrub (2026-10-09)

A `/export context` of the session wrote a transcript to `context.txt`
(untracked, already covered by `*.txt` in `.gitignore`). Because the token
had appeared in the transcript text, the export was sanitized:

```
python -I -c "..."  # replaces the literal token with ***REDACTED***
```

### Verification performed

| Check | Result |
| --- | --- |
| `grep -rIl <token> . --exclude-dir=.git` (working tree) | no match |
| `git log --all -p \| grep -c <token>` (all commits) | 0 |
| `git grep -l <token> HEAD -- .` (tracked files) | no match |
| `git config --get-regexp 'remote\..*'` | no token in remote URL |
| `.git/config` token grep | 0 |

The token the user authorized is short-lived by their own statement (they
revoke it once the work is done) and never entered version control.
