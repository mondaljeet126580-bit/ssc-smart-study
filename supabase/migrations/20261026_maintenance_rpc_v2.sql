begin;
drop function if exists public.get_app_maintenance();
create function public.get_app_maintenance()
returns jsonb
language sql stable security definer set search_path='public'
as $$
 select coalesce((select value from public.app_settings where key='maintenance'),jsonb_build_object('enabled',false,'message','The app is under maintenance. Please try again later.'));
$$;
revoke all on function public.get_app_maintenance() from public;
grant execute on function public.get_app_maintenance() to anon,authenticated;
create or replace function public.admin_set_maintenance(p_enabled boolean,p_message text)
returns jsonb
language plpgsql security definer set search_path='public'
as $$
declare e text; v jsonb;
begin
 if auth.uid() is null then raise exception 'Admin login required'; end if;
 select lower(trim(email)) into e from auth.users where id=auth.uid();
 if not exists(select 1 from public.admin_allowlist where lower(trim(email))=e and enabled=true) then raise exception 'Admin access denied'; end if;
 v=jsonb_build_object('enabled',coalesce(p_enabled,false),'message',left(coalesce(nullif(trim(p_message),''),'The app is under maintenance. Please try again later.'),500));
 update public.app_settings set value=v,updated_at=now() where key='maintenance';
 return v;
end;
$$;
revoke all on function public.admin_set_maintenance(boolean,text) from public;
grant execute on function public.admin_set_maintenance(boolean,text) to authenticated;
commit;
