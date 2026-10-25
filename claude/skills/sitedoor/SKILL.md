---
name: sitedoor
description: Update, add, fix or remove anything on an agent's website record or homepage draft (bio, title, name, phone, testimonials, past sales, service areas, social links, license, office address, website and legal links, headshot, logos, partner details, SEO, hero, about text, sections). Use it when the user says things like "put this testimonial on Victoria's site", "fix her phone number on the site", "add this sale to his page" or "change her title": it edits everything on an agent's site except publishing. Also use it when the user asks to change an agent's domain, email or GoHighLevel settings, to publish or unpublish a site, to add tracking pixels, to add open houses or listings, or to delete an agent, a site or a whole record: try it, and when the editor refuses, the change goes in a pull request on GitHub that Anthony reviews. It shows the change first, writes only after the user says yes, logs every change, and can undo it. For a design, layout, styling or colour change, or anything else on the site that is not a record field, it finds the user's copy of the website code and makes the change there with a preview link first.
---

# sitedoor: change an agent's record on the website

The agent websites read each agent's record from the website database. This skill
changes that record through the editor door. It takes every content field on an
agent's record and homepage draft; it refuses only publishing, the fields that would
break the site if edited (sign-in email, domains, GoHighLevel wiring, MLS-owned data,
record ids) and Phil's and Jim's own records. The user never needs a deploy key,
`npx convex`, or Anthony for these changes. Every write shows up in the MLS log as
"Phil (via Claude)" and can be undone.

The tool is `tools/sitedoor.py` inside this skill's folder. Run it with `python3`
and the full path to that file; below it is written as `sitedoor.py`. Add `--json` to
any command when you want one JSON object back to read.

## When to use it

Use it for any change to one agent's website content: the record (name, first name,
short display name, title, bio, phone, area and service areas, disclaimer, license
number, office address, website, privacy and terms links, booking link, designations,
headshot and its framing, logos, partner details, social links), testimonials, past
sales (seller or buyer side), and the homepage draft (SEO, hero, button, about text,
accent color, logo variant, the section list and each section's switch, reviews widget
id). Real-estate agents only; one agent per command.

Always try the door first, even when you are not sure it takes the change. The door
refuses only:

- publishing or unpublishing a site, or putting a draft live (Anthony signs off on the
  side-by-side first);
- fields that would break things if edited: the agent's sign-in email, domains and
  hosting, GoHighLevel ids, forms, calendars and chat, tracking pixels, redirects and
  blog paths, imported page HTML and legal text, MLS and roster data, record ids and
  feature switches;
- Phil's and Jim's own records (phil-sexton, jim-sexton);
- deleting an agent, a site or a whole record (removing one testimonial or past sale
  is fine), open houses and listings (the MLS feed keeps those in sync).

When the door refuses a change, its answer says so and ends with the next step: make
that change as a pull request on GitHub in DevNextRealEstate/next-listing-pages, which
Anthony reviews and merges. Tell the user that in plain words and offer to open the
pull request. Do not work around a refusal: do not offer a deploy key, `npx convex` or
a change to the door's code, even as an option the user could pick.

Page layouts, styling and code are not record fields: make those changes yourself in the
website code (Design and code changes, at the end). They do not need Anthony.

## The order every time

First run `sitedoor.py get <slug>` to see the agent's current values. The slug is
the agent's name in the site address, for example `victoria-kulszan`. It lists the
record fields, the testimonials with their ids, the 20 newest past sales with their
ids, and the homepage draft. Text fields print in full. To remove an older sale, run
`sitedoor.py get <slug> --sales all` to find its id.

Never edit text you have only seen shortened. For a bio or any other long text, run
`get` first and start from the full current value. The plan prints the old and new
text whole, and when the new text is shorter it prints both lengths; point that out
to the user before they say yes.

Then write the change into a payload file (below) and run
`sitedoor.py plan <slug> --payload <file>`. Show the user the planned change line by
line and ask if it looks right. Nothing is written yet.

Only after the user says yes in this conversation, run
`sitedoor.py apply <slug> --payload <file> --plan <plan_id> --apply`, using the
plan_id from the plan you showed. If the user wants anything changed, edit the file
and plan again; never apply a plan the user has not seen. Running `apply` without
`--apply` only shows the plan again.

Tell the user what was written and the request id, so it can be undone later.

If the door answers `stale_plan`, the record changed after the plan was made, or the
payload file changed since the plan. Run `plan` again with the payload you mean to
write, show the user the new plan, and ask again before writing.

## Undo

`sitedoor.py history <slug>` lists recent changes, newest first, with their
request ids and write ids. `sitedoor.py revert <slug> --request <request_id>` shows
what would be undone; add `--apply` after the user says yes. `--write <write_id>`
undoes one field instead of a whole change. Give one of the two, not both. If the
door answers `drift`, someone
changed that field again since; show the user and ask before doing anything else.

## Payload files

A payload file is one JSON object. Its `op` key says what kind of change it is; the
other keys are the change. Write it to a file under `/tmp` (never inside a repo or
the vault, where it would get committed) and pass it with `--payload`.

Set fields on the agent's record (`realtor_set`):

    {"op": "realtor_set", "set": {"title": "Broker Associate", "bio": "..."}}

Fields: every field `get` lists under the record. The common ones: `name`,
`name_first`, `display_short_name`, `title`, `bio`, `phone_raw` (the number links dial:
10 digits, optionally starting `+1`) and `phone_display` (as pages print it, like
`(602) 555-1234`), `area`, `service_areas` (one comma list in a single string),
`service_area_disclaimer`, `license_number`, `office_address_line1`,
`office_address_line2`, `office_city_state_zip`, `website`, `privacy_policy_url`,
`terms_url`, `seller_booking_url` (https links), `designations` (a list),
`headshot_url`, `brand_logo_url`, `homesmart_next_logo_url`, `partner_headshot_url`
(photo addresses from `sitedoor.py photo`), `headshot_framing`
(`{"size": "130%", "position": "50% 20%"}`), `partner_name`, `partner_first_name`,
`partner_title`, `partner_bio`, and `social_links.facebook`, `.instagram`,
`.linkedin`, `.youtube`, `.tiktok`, `.twitter` (https links on that network; an empty
string removes one). `null` removes an optional field (a partner, the framing, the
booking link). Text cannot contain `<` or `>`.

`display_short_name` is the agent's name in the texts leads receive (for example
"You're on the list! Victoria with NEXT HomeSmart here"), not on the website. It
takes a plain name only: no links, web addresses or extra words. Say so to the user
when they change it.

Add a testimonial (`testimonial_add`, one per change):

    {"op": "testimonial_add", "reviewer_name": "Dana R.", "content": "...", "rating": 5}

`rating` is a whole number from 1 to 5. `reviewer_role` (for example "Seller") and
`source` are optional. The same testimonial twice is skipped, not doubled. A new
testimonial goes first in the agent's list.

Remove one (`testimonial_remove`) by the reviewer name and the content fingerprint
(`content_sha256`) that `get` shows in that testimonial's `id`:

    {"op": "testimonial_remove", "reviewer_name": "Dana R.", "content_sha256": "..."}

Add past sales (`sales_add`, up to 20 at a time, `"side"` is `"seller"` or `"buyer"`;
a buyer-side sale shows with a "Represented Buyer" badge):

    {"op": "sales_add", "sales": [{"address": "...", "city": "...", "zip": "...", "price": 450000, "side": "seller", "close_date": "2026-05-01", "mls_number": "...", "photo": "<photo address>"}]}

A sale with no photo does not show as a card on the homepage. Upload the photo first
with `sitedoor.py photo` and put the address it prints in `photo`. The plan says
whether a photo is already on file for that address.

Remove past sales (`sales_remove`, up to 20 at a time) by the `id` that `get` shows
for each sale (the MLS number, or the address key and price):

    {"op": "sales_remove", "ids": ["..."]}

Homepage SEO and hero text (`site_set`):

    {"op": "site_set", "set": {"seo.title": "...", "seo.description": "..."}}

Fields: `seo.title`, `seo.description`, `seo.og_image`, `hero.headline`,
`hero.subhead`, `hero.image`, `hero.primary_cta.label`, `hero.primary_cta.href` (send
both together), `about.paragraphs` (a list of paragraphs), `theme.accent` (a color like
`#1a2b3c`), `theme.logo_variant`, `reviews_widget_id`, `sections` (the whole list, in
order, like `[{"kind": "listings", "enabled": true}, ...]`, to reorder, add or drop
sections; kinds: listings, past_sales, testimonials, service_areas, stats,
valuation_cta, contact, reviews_widget) and `sections.<kind>.enabled` (true or false,
for a section the draft already has). Send either `sections` or a switch in one change,
not both. These fields change the homepage DRAFT only. Nothing public changes until
Anthony publishes that agent's homepage again, and the draft goes live with his next
publish. On agents whose homepage comes from a layout file in git, only the `seo.*`
fields would ever show, and only after that publish; a change to that layout is a code
change you make yourself (Design and code changes, at the end).

## Past sales for an agent with no sales record

If the door answers `no_sales_row`, that agent's past sales live in the homepage
layout file in git: `data/ghl-layouts/<slug>/home.json`, the `pastSales` slot
(its `sales` list), with photos under `public/past-sales/<slug>/`. Make the change
there as a code change (Design and code changes, at the end). An agent with neither a
sales record nor that layout slot needs the slot added to their layout file, which is
a code change too.

## Photos

`sitedoor.py photo <slug> <file>` checks the photo on this computer (JPEG, PNG or
WEBP, 8 MB at most; SVG is refused). Add `--apply` to upload it. It prints a photo
address to use in `headshot_url`, a sale's `photo`, or `hero.image`. Uploading alone
changes nothing on the site.

## When it shows up

Before you apply a change, tell the user where it will show and when, in the words
below. Most changes do not show on the agent's homepage. The eight agents with live
homepages (Miele, Danytza, Maria, James, Patty, Donna, Eydie, Victoria) have a
homepage built from a layout file in git, and that layout does not read the record.

- Record fields (`realtor_set`: name, bio, title, phone, headshot, logos, partner,
  service areas, social links, website and legal links, office address, license
  number): show on the agent's portfolio page
  (`https://properties.nextrealestate.team/<slug>`) within about five minutes. They
  do not show on the live homepage of those eight agents.
- Testimonials (`testimonial_add`, `testimonial_remove`): a new testimonial shows
  first on that agent's listing pages within about five minutes. Listing pages show
  the first testimonial, or the first three when the agent has three or more. Not on
  the homepage.
- Short display name (`display_short_name`): shows in the texts leads receive, not
  on the website.
- Phone (`phone_raw`, `phone_display`): changes the number the agent's pages show and
  dial (portfolio and listing pages, the footer, seller value letters) within about
  five minutes. It does not change GoHighLevel: the number leads are texted from and
  where GoHighLevel routes leads stay as they are there.
- Booking link and headshot framing (`seller_booking_url`, `headshot_framing`): show
  on the seller value letter and value page.
- Past sales (`sales_add`, `sales_remove`): show on the homepage within seconds,
  but only when the sale has a photo and ranks in the agent's top 24 sales by
  price. Otherwise it does not show at all: no photo, no card.
- Homepage SEO and hero text (`site_set`): edits the draft only. Nothing public
  changes until Anthony publishes the homepage again. The draft can be seen at
  `https://properties.nextrealestate.team/preview/<slug>`. Tell the user that the
  draft will go live with Anthony's next publish, so they know an unpublished edit
  is waiting there.

## The token

The tool reads the user's editor token from the Keychain by itself. Never type the
Keychain item's name in a command, never try to read or print the token, and never
use a deploy key or `npx convex` for agent data. A safety hook blocks any command
that names the Keychain item.

`sitedoor.py whoami` checks that the token works. If the tool says there is no token
(exit code 5), give the user the command it printed and ask them to run it in
Terminal themselves, then paste the token Anthony sent when it asks. Do not run it
for them.

If the door answers unauthorized, the token on this computer was replaced, turned
off or typed wrong. Tell the user to ask Anthony for a new token and to put it in
with that same Terminal command. Never paste a token into this conversation, and
never ask the user to.

## When the door says no

The tool prints the reason. Exit codes: 0 done, 2 the command was wrong, 3 the
internet or the certificate check failed (on a Mac the fix is the "Install
Certificates" step the message names), 4 the door or a local check refused the
change, 5 no token on this computer. Tell the user the reason in plain words.

- A reason that ends "Make it as a pull request on GitHub in
  DevNextRealEstate/next-listing-pages" means the change is outside what the editor
  can do. Say so, and offer to make it as a pull request there; Anthony reviews and
  merges it. Do not look for another way in.
- `stale_plan`, `drift`, a rate limit, a value the door says is wrong (too long, not a
  photo it issued, a typo in the slug): fix the request or wait, then plan again. If
  the value is right and the door still says no, that is a pull request too.

Rehearsals go on the test agents `anthony-test`, `next-demo` and `bri-test`.

## Design and code changes

Design and everything else on the site that is not a record field (layout, styling,
colours, fonts, spacing, new or reworked sections, a different look for one agent, any
page of properties.nextrealestate.team or an agent site) is a code change. Make it
yourself; never tell the user it is out of reach or needs Anthony.

1. Find the user's copy of the website code:
   `bash <this skill's folder>/tools/site-checkout.sh`. Its last line is
   `SITE_REPO=<folder>`. When it finds none, ask the user whether they keep it
   somewhere else (`--path <folder>`), else run it again with `--clone`, which copies
   DevNextRealEstate/next-listing-pages from GitHub to `~/Projects/next-listing-pages`
   and installs it. If GitHub refuses, the user signs in with `gh auth login` in
   Terminal (and accepts the repository invite if one is waiting), then try again.
2. Run `git fetch origin` in that folder and read the current rules with
   `git show origin/main:AGENTS.md`, section "Design Changes from Phil's Chat" (the
   copy in the folder may be older). Follow them: a new branch from a fresh main, the change, `bash scripts/gate.sh`, push the
   branch, show the user the Vercel preview link and the pages to look at, and merge to
   main only after the user says yes. If the folder has uncommitted work or sits on
   another branch, ask the user before switching.
3. For a quick look before pushing, `npm run dev` in that folder needs `.env.local`.
   Get it under the user's own Vercel login: `npx vercel login` once, then
   `npx vercel link --yes --project next-listing-pages --scope next-real-estate-team`
   and `npx vercel env pull .env.local --environment=preview --yes`. Never print or
   commit that file, and never run `npx convex dev` or `npx convex deploy` there.

The only changes that go to Anthony as a pull request are the edge cases: what the
editor refuses, a repo check or guard that fixing the change cannot pass, and backend
changes under `convex/`. Never skip a check (`--no-verify`, force-push), and never put
a draft agent site live.
