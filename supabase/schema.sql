-- AInstein on Supabase. Run the whole file once in Supabase → SQL Editor → Run.
-- Safe to run again: it only creates what's missing and replaces the policies.
--
-- Also, in the Supabase dashboard:
--   Authentication → Sign In / Providers → Allow anonymous sign-ins: ON
--   Authentication → URL Configuration → Site URL: your Vercel address
--     (e.g. https://a-instein.vercel.app) and add it under Redirect URLs too,
--     or the sign-in link in the email won't bring people back to the site.

-- ---------------------------------------------------------------------------
-- 1. Each visitor's diary (private). Anonymous visitors get one too.
create table if not exists public.user_data (
  user_id    text primary key,
  state      jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.user_data enable row level security;
drop policy if exists "read own row"   on public.user_data;
drop policy if exists "insert own row" on public.user_data;
drop policy if exists "update own row" on public.user_data;
create policy "read own row"   on public.user_data for select using (auth.uid()::text = user_id::text);
create policy "insert own row" on public.user_data for insert with check (auth.uid()::text = user_id::text);
create policy "update own row" on public.user_data for update using (auth.uid()::text = user_id::text)
                                                             with check (auth.uid()::text = user_id::text);

-- ---------------------------------------------------------------------------
-- 2. Everything social, in one table of small JSON documents:
--    likes, profiles, follows, comments, suggestions, chat (rooms),
--    dm (messages), reports, mod (moderation), and private per-user docs.
create table if not exists public.docs (
  collection text not null,
  id         text not null,
  owner      text not null default auth.uid()::text,
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (collection, id)
);
create index if not exists docs_collection on public.docs (collection);

-- Who may moderate (hide messages, ban). Add yourself after your first sign-in.
create table if not exists public.admins (user_id text primary key);
alter table public.admins enable row level security;
drop policy if exists "anyone reads admins" on public.admins;
create policy "anyone reads admins" on public.admins for select using (true);

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.admins where user_id = auth.uid()::text)
$$;

-- A signed-in person (not an anonymous visitor).
create or replace function public.is_member() returns boolean
language sql stable as $$
  select auth.uid() is not null and coalesce((auth.jwt() ->> 'is_anonymous')::boolean, false) = false
$$;

-- The write rule, one place:
--   likes, profiles, follows: one document per person, id = your user id;
--     anonymous visitors may write these too.
--   chat, dm, reports: the same, but only for signed-in members.
--   comments, suggestions: any id, but the author inside must be you.
--   data/users/<your id>: your private documents.
--   mod: admins only.
create or replace function public.may_write(col text, doc_id text, body jsonb) returns boolean
language sql stable as $$
  select case
    when col like 'data/users/%' then col = 'data/users/' || auth.uid()::text
    -- a page, likes and follows: any visitor, even before signing in
    when col in ('likes','profiles','follows') then doc_id = auth.uid()::text
    -- saying anything to other people needs a signed-in (email) account
    when not public.is_member() then false
    when col in ('chat','dm','reports') then doc_id = auth.uid()::text
    when col in ('comments','suggestions') then coalesce(body ->> 'uid', '') = auth.uid()::text
    when col = 'mod' then public.is_admin()
    else false
  end
$$;

alter table public.docs enable row level security;
drop policy if exists "read docs"   on public.docs;
drop policy if exists "insert docs" on public.docs;
drop policy if exists "update docs" on public.docs;
drop policy if exists "delete docs" on public.docs;

create policy "read docs" on public.docs for select
  using (collection not like 'data/users/%' or collection = 'data/users/' || auth.uid()::text);
create policy "insert docs" on public.docs for insert
  with check (owner = auth.uid()::text and public.may_write(collection, id, data));
create policy "update docs" on public.docs for update
  using ((owner = auth.uid()::text or (collection = 'mod' and public.is_admin())))
  with check (owner = auth.uid()::text and public.may_write(collection, id, data));
create policy "delete docs" on public.docs for delete
  using (owner = auth.uid()::text);

-- Live updates (likes and messages appear without reloading).
do $$ begin
  alter publication supabase_realtime add table public.docs;
exception when duplicate_object then null; end $$;

-- ---------------------------------------------------------------------------
-- 3. Make yourself the moderator — run AFTER you've signed in on the site once:
-- insert into public.admins (user_id)
--   select id::text from auth.users where email = 'YOUR EMAIL HERE'
--   on conflict do nothing;
