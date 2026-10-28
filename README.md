# SSC Smart Study — Admin Console

This repository contains the separate admin console for the Study Chat / ChatLink system.

## Admin login

The admin console now uses the same **Username + 6-digit PIN** authentication style as the ChatLink account system.

- No Google login.
- No Gmail login screen.
- Admin login fields: username + 6-digit PIN.
- New account creation uses the existing `user-auth` Supabase Edge Function.
- The PIN is handled by Supabase Auth as the password and is never stored as plaintext in GitHub.
- The browser only receives the Supabase publishable key; the service-role key remains inside Supabase Edge Functions.
- On page open, the console restores a saved Supabase session and verifies it with the server-side admin dashboard endpoint. If the session is still valid and the account is allowlisted, the dashboard opens directly; if there is no valid session, the Username + Password login screen appears.
- The console shows a full-screen loading indicator while checking the saved session and preparing the first dashboard view. The first dashboard response is reused for rendering to avoid a duplicate dashboard request.

## Admin permission

Authentication and admin permission are separate. A valid Username + PIN account does **not** automatically become an administrator.

The server-side `admin-console` Edge Function checks `public.admin_allowlist` before returning admin data or allowing moderation actions.

For a username such as `YOUR_ADMIN_USERNAME`, the internal Auth email used by this project is:

    YOUR_ADMIN_USERNAME@username.ssc-smart-study.local

After creating the admin account, add that exact internal email to `public.admin_allowlist` with `enabled = true`. Do not add normal users.

Example SQL:

    insert into public.admin_allowlist(email, enabled)
    values ('YOUR_ADMIN_USERNAME@username.ssc-smart-study.local', true)
    on conflict (email) do update set enabled = true;

## Admin features

- Total user count
- Online users
- Banned users
- Total messages
- Conversation count
- Recent messages
- User search by name/username
- Per-user conversation history
- Message history and delivery/read timestamps when available
- Image preview in admin details
- Ban / unban users
- Delete user account
- Delete individual messages
- Admin audit log

## Supabase components

- `index.html` — admin UI and Username + PIN login.
- `user.html` — the same Username + 6-digit PIN user authentication UI.
- `supabase/functions/user-auth/index.ts` — secure account creation using a private internal Auth email identity.
- `supabase/functions/admin-console/index.ts` — server-side admin authorization, dashboard, user/message inspection and moderation.
- `supabase/migrations/20261026_admin_console.sql` — database/RLS/admin tables and chat hardening.

## GitHub Pages

Publish `main` from the repository root.

Admin page:

    https://mondaljeet126580-bit.github.io/ssc-smart-study/

User login page:

    https://mondaljeet126580-bit.github.io/ssc-smart-study/user.html

## Security

- Never put a Supabase service-role/secret key in `index.html` or `user.html`.
- Keep `admin_allowlist` restricted to the intended admin account(s).
- Admin actions are recorded in `admin_audit_logs`.
- Supabase Auth handles password/PIN verification; the PIN is not stored in the public `profiles` table.
