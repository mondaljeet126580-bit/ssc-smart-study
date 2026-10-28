-- Add user-submitted message reports for scoped, audited admin chat review.
begin;
create table if not exists public.message_reports (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references public.conversations(id) on delete cascade,
  message_id uuid not null references public.messages(id) on delete cascade,
  reported_by uuid not null references auth.users(id) on delete cascade,
  reason text not null check (char_length(btrim(reason)) between 3 and 500),
  status text not null default 'pending' check (status in ('pending','in_review','resolved','dismissed')),
  created_at timestamptz not null default now(),
  reviewed_at timestamptz,
  reviewed_by uuid references auth.users(id) on delete set null,
  moderation_notes text check (moderation_notes is null or char_length(moderation_notes) <= 1000)
);
create index if not exists message_reports_status_created_idx
  on public.message_reports(status, created_at desc);
create index if not exists message_reports_conversation_status_idx
  on public.message_reports(conversation_id, status, created_at desc);
create unique index if not exists message_reports_one_active_per_reporter_message_idx
  on public.message_reports(reported_by, message_id)
  where status in ('pending','in_review');
alter table public.message_reports enable row level security;
revoke all on table public.message_reports from anon, authenticated;
grant select, insert on table public.message_reports to authenticated;
grant all on table public.message_reports to service_role;
drop policy if exists "Users can read their own message reports" on public.message_reports;
create policy "Users can read their own message reports"
  on public.message_reports for select to authenticated
  using (reported_by = (select auth.uid()));
drop policy if exists "Conversation members can report another user's message" on public.message_reports;
create policy "Conversation members can report another user's message"
  on public.message_reports for insert to authenticated
  with check (
    reported_by = (select auth.uid())
    and not private.is_user_banned((select auth.uid()))
    and private.is_conversation_member(conversation_id, (select auth.uid()))
    and exists (
      select 1
      from public.messages m
      where m.id = message_reports.message_id
        and m.conversation_id = message_reports.conversation_id
        and m.sender_id <> (select auth.uid())
        and m.deleted_at is null
        and not m.delete_for_everyone
    )
  );
comment on table public.message_reports is
  'User-submitted chat moderation reports. Full transcript access is restricted to the allowlisted admin-console Edge Function and audited per case.';
commit;