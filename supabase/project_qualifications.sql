create table if not exists public.project_qualifications (
  project_id text primary key,
  status text not null default 'new' check (status in ('new', 'to_qualify', 'interested', 'in_contact', 'archived')),
  notes text not null default '',
  history jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.project_qualifications enable row level security;

drop policy if exists "project_qualifications_select_anon" on public.project_qualifications;
create policy "project_qualifications_select_anon"
on public.project_qualifications
for select
to anon
using (true);

drop policy if exists "project_qualifications_insert_anon" on public.project_qualifications;
create policy "project_qualifications_insert_anon"
on public.project_qualifications
for insert
to anon
with check (true);

drop policy if exists "project_qualifications_update_anon" on public.project_qualifications;
create policy "project_qualifications_update_anon"
on public.project_qualifications
for update
to anon
using (true)
with check (true);

create or replace function public.set_project_qualification_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists project_qualifications_set_updated_at on public.project_qualifications;
create trigger project_qualifications_set_updated_at
before update on public.project_qualifications
for each row
execute function public.set_project_qualification_updated_at();
