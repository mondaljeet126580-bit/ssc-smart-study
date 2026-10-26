# Study Chat Admin Console

This repository now contains only the admin console and its required Supabase source files. The browser receives only the Supabase publishable key; no service-role key is committed.

## Included files

- index.html — responsive Bengali admin UI and Google sign-in.
- supabase/functions/admin-console/index.ts — server-side authentication, allowlist checks, dashboard/user/message reads, ban/unban, account/message deletion and audit logs.
- supabase/migrations/20261026_admin_console.sql — allowlist/audit tables, moderation fields, RLS enforcement and RPC hardening.
- supabase/config.toml — function configuration.

## One-time setup required

### Google OAuth in Supabase

Google login cannot be activated by HTML code alone. You must create a Google OAuth Client ID and Client Secret:

1. In Google Cloud Console → Google Auth Platform → Clients, create an OAuth Client ID of type Web application.
2. Authorized JavaScript origin: https://mondaljeet126580-bit.github.io
3. Authorized redirect URI: https://mtitrkspgoqaqdeiluud.supabase.co/auth/v1/callback
4. In Supabase Dashboard → Authentication → Sign In / Providers → Google, enable Google and paste that Client ID and Client Secret.
5. In Supabase → Authentication → URL Configuration:
   - Site URL: https://mondaljeet126580-bit.github.io/ssc-smart-study/
   - Add Redirect URL: https://mondaljeet126580-bit.github.io/ssc-smart-study/

Google OAuth availability was not confirmed by the database checks. If Google is not already enabled in this Supabase project's provider settings, complete the steps above before using sign-in.

### Allow only your Gmail

The admin allowlist is intentionally empty by default. Add only the exact verified Gmail you will use for admin login by running this in Supabase SQL Editor (replace the example address):

    insert into public.admin_allowlist(email, enabled)
    values ('YOUR-GMAIL@gmail.com', true)
    on conflict (email) do update set enabled = true;

The Edge Function checks this list on every admin request. Do not grant all Google users access.

### Publish on GitHub Pages

Open GitHub → Settings → Pages, choose Deploy from a branch, branch main, folder / (root), then Save. When published, open:

    https://mondaljeet126580-bit.github.io/ssc-smart-study/

## Privacy and safety

- Every admin API call validates a Supabase session and the confirmed email allowlist.
- Viewing a user's conversation detail, viewing users/dashboard, bans/unbans and deletion actions are written to admin_audit_logs.
- A ban is enforced in RLS and chat RPCs as well as in the Auth account, not only hidden in the UI.
- Delete account is destructive: it deletes the account, profile, every conversation the user belongs to, all messages in those conversations, and associated chat images. Other participants lose that conversation history too. The UI asks twice before deletion.
- Read status is based on stored read_at/delivered_at timestamps. Older messages with no receipt timestamp may show an unknown status.
- Service-role credentials must stay in Supabase's server environment and must never be placed in index.html or committed to GitHub.

## Deployment

The admin-console Edge Function source is included at supabase/functions/admin-console/index.ts and is deployed to Supabase with JWT verification enabled. The database changes have already been applied to project mtitrkspgoqaqdeiluud.