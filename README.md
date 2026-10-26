# SSC Smart Study — Admin + Username/PIN Login

The repository contains the admin console plus a separate user login page. The browser receives only the Supabase publishable key; no service-role key is committed.

## Included files

- `index.html` — responsive Bengali admin UI and Google sign-in.
- `user.html` — user account creation/login using username + 6-digit PIN; no email is shown to users.
- `supabase/functions/admin-console/index.ts` — server-side admin authentication, allowlist checks, dashboard/user/message reads, moderation and audit logs.
- `supabase/functions/user-auth/index.ts` — secure server-side account creation. It creates the Supabase Auth account with a private internal email identity and stores the public username/display name in `profiles`.
- `supabase/migrations/20261026_admin_console.sql` — moderation fields, RLS enforcement and chat RPC hardening.

## Username + PIN login

Open:

    https://mondaljeet126580-bit.github.io/ssc-smart-study/user.html

New users choose a username, display name and a 6-digit PIN. The PIN is handled by Supabase Auth as the password; it is not stored as plain text in the database or GitHub. Returning users log in with the same username and PIN. Usernames are unique (case-insensitive).

The server-side `user-auth` Edge Function uses the Supabase service-role credential only inside Supabase and never sends it to the browser.

## Admin login

`index.html` remains the separate admin console. Google OAuth setup and the exact admin Gmail allowlist are described below. Do not make the user login page an admin login; normal users must never receive admin permissions.

## Google OAuth in Supabase

Google login for the admin console cannot be activated by HTML alone. If you want Google admin login, create an OAuth Client ID of type Web application in Google Cloud and configure the Supabase callback:

    https://mtitrkspgoqaqdeiluud.supabase.co/auth/v1/callback

Then enable Google in Supabase Authentication → Sign In / Providers and configure the GitHub Pages URL under Authentication → URL Configuration.

## Allow only your Gmail

The admin allowlist is intentionally empty by default. Add only the exact verified Gmail used for admin login in Supabase SQL Editor.

## Publish on GitHub Pages

GitHub → Settings → Pages → Deploy from a branch → `main` → `/ (root)`.

User login page:

    https://mondaljeet126580-bit.github.io/ssc-smart-study/user.html

Admin page:

    https://mondaljeet126580-bit.github.io/ssc-smart-study/

## Privacy and safety

- User PINs are never stored as plain text.
- Username uniqueness is enforced with a database unique index.
- A banned account is rejected by the user UI and enforced by chat RLS/RPC rules.
- Service-role credentials stay only inside Supabase Edge Functions and are never committed to GitHub.
- Admin actions remain audited.

## Deployment

The `user-auth` Edge Function is deployed to Supabase project `mtitrkspgoqaqdeiluud` with its service-role credential kept server-side. The admin-console function remains separately deployed with JWT verification enabled.
