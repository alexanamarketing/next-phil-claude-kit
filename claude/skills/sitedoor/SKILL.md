---
name: sitedoor
description: Update, add, fix or remove something on an agent's record in the website database (bio, title, testimonials, past sales, service areas, social links, license number, office address, headshot photo, homepage SEO text). Use it when the user says things like "put this testimonial on Victoria's site", "fix her bio on the site", "add this sale to his page" or "change her title". Also use it when the user asks to change an agent's domain, phone, email or GoHighLevel settings, to publish or unpublish a site, to add tracking pixels, to add open houses or listings, or to delete an agent, a site or a whole record, so the answer says plainly that this is not done this way and Anthony handles it. It shows the change first, writes only after the user says yes, logs every change, and can undo it.
---

# sitedoor: change an agent's record on the website

The agent websites read each agent's record from the website database. This skill
changes that record through the editor door, a narrow entrance that accepts only the
fields listed below. The user never needs a deploy key, `npx convex`, or Anthony for
these changes. Every write shows up in the MLS log as "Phil (via Claude)" and can be
undone.

The tool is `tools/sitedoor.py` inside this skill's folder. Run it with `python3`
and the full path to that file; below it is written as `sitedoor.py`. Add `--json` to
any command when you want one JSON object back to read.

## When to use it

Use it for a change to one agent's record: bio, title, first name or short display
name, area and service areas, service area disclaimer, social links, license number,
office address, headshot photo, testimonials, past sales, and the homepage draft's
SEO and hero text (draft only, see "When it shows up"). Real-estate agents only; one
agent per command.

It cannot change domains, phone numbers or email addresses. It cannot publish or
unpublish a site, delete an agent, a site or a whole record (removing one
testimonial or past sale is fine), touch GoHighLevel, change tracking pixels, or add
open houses. It never touches listings (the MLS feed keeps those in sync). If the user asks for
one of those, say plainly that this tool does not do it and that Anthony handles it.
Do not look for another way in: do not offer a deploy key, `npx convex` or a change
to the door's code, even as an option the user could pick.

Page layouts and code still go through git the way the user already works.

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

If the door answers `stale_plan`, the record changed after the plan was made. Run
`plan` again, show the user the new plan, and ask again before writing.

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

Fields: `bio`, `title`, `name_first`, `display_short_name`, `area`, `service_areas`
(one comma list in a single string), `service_area_disclaimer`, `license_number`,
`office_address_line1`, `office_address_line2`, `office_city_state_zip`,
`headshot_url` (a photo address from `sitedoor.py photo`), and
`social_links.facebook`, `.instagram`, `.linkedin`, `.youtube`, `.tiktok`,
`.twitter` (https links on that network; an empty string removes one). Text cannot
contain `<` or `>`.

Add a testimonial (`testimonial_add`, one per change):

    {"op": "testimonial_add", "reviewer_name": "Dana R.", "content": "...", "rating": 5}

`rating` is a whole number from 1 to 5. `reviewer_role` (for example "Seller") and
`source` are optional. The same testimonial twice is skipped, not doubled.

Remove one (`testimonial_remove`) by the reviewer name and the content fingerprint
(`content_sha256`) that `get` shows in that testimonial's `id`:

    {"op": "testimonial_remove", "reviewer_name": "Dana R.", "content_sha256": "..."}

Add past sales (`sales_add`, up to 20 at a time, seller side only):

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
`hero.subhead`, `hero.image`, `hero.primary_cta.label`, `hero.primary_cta.href`,
`about.paragraphs` (a list of paragraphs), `theme.accent` (a color like `#1a2b3c`),
and `sections.<kind>.enabled` (true or false, for a section the page already has:
listings, past_sales, testimonials, service_areas, stats, valuation_cta, contact,
reviews_widget). These fields change the homepage DRAFT only. Nothing public
changes until Anthony publishes that agent's homepage again, and the draft goes live
with his next publish. On agents whose homepage comes from a layout file in git, only
the `seo.*` fields would ever show, and only after that publish.

## Past sales for an agent with no sales record

If the door answers `no_sales_row`, that agent's past sales live in the homepage
layout file in git: `data/ghl-layouts/<slug>/home.json`, the `pastSales` slot
(its `sales` list), with photos under `public/past-sales/<slug>/`. Make the change
there and commit it the way the user already does. Only an agent with neither a
sales record nor that layout slot needs Anthony.

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

- Record fields (`realtor_set`: bio, title, headshot, service areas, social links,
  office address, license number): show on the agent's portfolio page
  (`https://properties.nextrealestate.team/<slug>`) within about five minutes. They
  do not show on the live homepage of those eight agents.
- Testimonials (`testimonial_add`, `testimonial_remove`): show on that agent's
  listing pages within about five minutes (the first three). Not on the homepage.
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
change, 5 no token on this computer. Tell the user the reason in plain words. If the
door refuses a field or an agent, that is on purpose; do not work around it.

Rehearsals go on the test agents `anthony-test`, `next-demo` and `bri-test`.
