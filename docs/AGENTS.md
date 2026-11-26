# Rules for AI agents (paste into CLAUDE.md / AGENTS.md / your system prompt)

```
## Browser work: use Chrome Profile Hub
- Never launch a fresh Playwright Chromium for sites that need a login (Google blocks it).
- Find a profile:   python -m chrome_profile_hub pick <service> [--owner X]
  services: google notion facebook slack zalo tiktok lark hubspot instagram github claude linkedin x shopee
- Attach:           from chrome_profile_hub import open_chrome, agent_page
                    browser, ctx = open_chrome(p, "<email or key>", task="<short task name>")
                    page = agent_page(ctx, url)      # your own tab, auto-closed when the script exits
- NEVER call browser.close(), never touch tabs you did not open, never delete profiles or cookies.
- If no profile has the login (or you land on a sign-in page): STOP and ask the human to open the hub,
  right-click the row -> "Log in again..." -> service. Do not type passwords or 2FA codes yourself.
- Prefer reading page text (page.inner_text / locators) over screenshots: far fewer tokens.
```

Why these rules:
- **Real Chrome + CDP** keeps Google happy and lets one human login serve many agent runs.
- **Own tab + lease** means the human and several agents can share one window without stepping on each other.
- **Humans own credentials.** The agent never sees or types a password; it only reuses an existing session.
