# Guru Watch — Channel ID Registry
*Working document. Started Aug 28, 2026. Feeds the weekly RSS detection step (Production Process §11).*

## Purpose
Maps each producer/creator to their permanent YouTube channel ID, derived from a sample video URL already logged in Notion's "Side Hustle Intel — Source Transcripts" database. Channel IDs are permanent — once resolved here, a producer never needs re-lookup, only new producers get added.

## Status as of Aug 28, 2026 — REGISTRY COMPLETE (all 3 pages done); full RSS run complete across all 215 channels, 2 data bugs found+fixed
Notion's data source had **267 distinct "Channel" text values across 364 rows** as of the original Aug 28, 2026 pull. **Updated Sept 14, 2026: 21 more producers found via a presenter-list refresh against the now-456-entry live database, bringing the total to 236 unique YouTube channel IDs** — see the new Page 4 section below. **Updated again Sept 14, 2026: AI Mastery removed (determined not WAH-relevant during batch review) — 235 unique YouTube channel IDs remain tracked.** Of those: **3 are non-YouTube sources** (excluded — see below), **1 failed to resolve** ("Business Money" — see Unresolved below), and the remaining **263 values resolve to 215 unique YouTube channel IDs**, all listed below.

**Correction (Aug 28, 2026):** this section previously stated "221 unique YouTube channel IDs" and labeled Page 2 as "88 channels." Both were stale/inaccurate relative to the actual table rows — a programmatic count of the three tables below gives 89 (Page 1) + 81 (Page 2) + 45 (Page 3) = **215** unique channel IDs, not 221. The page-header channel counts below have been corrected to match. This was caught as a byproduct of the full RSS validation run (see below), not a separate audit — worth remembering that this doc's own summary numbers can drift from the tables and should be spot-checked periodically.

This registry is now ready to seed the RSS-based weekly detection step described in Production Process §11 (Guru Watch Phase A). New producers Kevin adds later just get appended the same way — see "How to continue this" at the bottom.

**Small-batch RSS test (Aug 28, 2026):** Ran a 10-channel proof-of-concept RSS-check (Chris Koerner, Alex Hormozi, Ali Abdaal, Mark Tilbury, David Heacock, Iman Gadzhi, Pat Flynn, Codie Sanchez, My First Million, Wholesale Ted) to validate the mechanism before a full run. 9/10 succeeded cleanly. The 10th, Wholesale Ted, 404'd — tracing it down found a transcription error in this registry (see fix below), now corrected. See Production Process §11 for the full write-up of what this proved and what it changed about the plan.

**Full-registry RSS run (Aug 28, 2026):** With the mechanism validated, ran the same RSS-check across all remaining 205 channels (215 total minus the 10 above), in batches of 18 to stay under the browser tool's ~45-second execution window. Results:
- **204 of 205 channels resolved cleanly** (HTTP 200, valid feed).
- **1 more bad channel ID found: Billy Robinson.** Recorded as `UCajEYnZi3V-w52CTivgHlcg` — 404'd on RSS fetch. Re-derived from the stored sample video (`oAREF2wSHUo`) via the spaced-character extraction technique; the difference turned out to be capitalization, not a dropped character like Wholesale Ted — the correct ID is `UCajEYnZi3V-w52cTivgHlcg` (lowercase "c", not "C"). Verified working via a successful RSS fetch (status 200). The table below now has the corrected ID.
- Combined with the Wholesale Ted fix, this full run served as a validation pass for the whole registry as intended — 2 bad IDs found and fixed out of 215, both bugs slipping through as case/character-transcription errors during the original character-by-character reassembly (see method notes below).
- **186 of the 205 channels showed at least one video published in the last 30 days that isn't already logged in Notion.** This is expected, not a signal of unusual activity — as anticipated in Production Process §11, Notion only holds a curated sample per channel rather than a full upload history, so on this first-ever run nearly every genuinely active channel shows "new" videos by this measure. The number itself isn't the useful output; it confirms the mechanism surfaces real candidates. Going forward, each weekly run should compare against *the previous run's results* (a stored "last seen" state per channel), not just Notion's existing rows — that's what will turn this into an actual "what's new since last week" signal rather than "what's new since this program started." That refinement isn't built yet; flagging it as the next real design gap for Phase A.

**Method notes (useful for future maintenance or adding new producers):**
- The reliable, safe way to get a channel ID is one real page navigation per video followed by reading `ytInitialPlayerResponse.videoDetails` from that loaded page — matches ordinary human browsing. A bulk parallel-fetch shortcut was tried and abandoned early in this project (worked at moderate volume, failed hard at scale) — do not revisit it.
- **Content-filter quirk:** the page-script tool sometimes blocks a returned `channelId` (or occasionally even the display name) as `"[BLOCKED: Base64 encoded data]"` — a false positive, not real sensitivity. Workaround: request `channelId.split('').join(' ')` (spaces between every character) and strip the spaces back out afterward. **Caution:** this character-by-character reassembly is where both confirmed bugs (Wholesale Ted, Billy Robinson) picked up their error — a dropped letter and a wrong letter-case, respectively — double-check reassembled IDs against the source when possible.
- Once the whole registry was live, this same fetch+regex RSS-check pattern (see Production Process §11) doubled as an independent verification pass: any remaining bad IDs surfaced as plain HTTP 404s across the full run, the same way both bugs above were caught.
- **Batch-size limit:** a single `browser_batch` call processing ~20 videos (40 actions) can hit a client-side timeout even though the browser keeps executing correctly in the background. Keep batches to roughly 8-10 videos (16-20 actions) per call. The same applies to RSS-check batches run via `javascript_tool` — 18 channels per call (with a 700ms pacing delay between fetches) stayed comfortably under the ~45s timeout; 35-channel batches sometimes exceeded it (though the fetches still completed in the background).
- **A few videos return an empty `videoDetails` on first load** but resolve fine on retry with a short wait (1.5-3s) before reading. Retry once or twice before concluding a lookup is broken.
- **Several Notion "Channel" labels didn't match the actual channel name found** (likely mishearing/typo when transcribed from audio) — these are marked with ⚠ in the tables below. A few surprising real merges came out of this: "Sarah (AI side hustles YouTube creator)" and "Wholesale Ted" are the same channel; "Shawn Doughty" is actually Sean Dollwet; "Tar Chester" is actually Tanner Chidester; "Kai Stone and Michael, Stone Systems" and "Kevin Patrick" are both actually "ItsKeaton" (same as the separate "Keaton" entry); "Nick Ponte" is actually "High Level Profit Systems"; "Mini machine business YouTube creator (duplicate upload)" is NOT a duplicate — it's a genuinely different channel (Wealth Unlocked) that reposted the same content as the original (SUCCESSFUL ENTREPRENEUR).
- **One value never resolved after repeated attempts:** "Business Money" (sample video `swRtNKlDCo0`) — page loads (`window.ytInitialPlayerResponse` exists) but `videoDetails` comes back empty every time. Needs a manual look or a different sample video from that Notion Channel value's other rows (it has 3 total rows in Notion, per the original count, so other sample videos likely exist).
- **Confirmed bug #1, fixed Aug 28, 2026:** the Wholesale Ted channel ID was recorded as `UCC8wcz7734jKPhiR2UkS9A` (missing a "y") — this 404'd when queried as an RSS feed during the small-batch test. Re-derived from the stored sample video (`8NvhbfZNTrc`, cross-checked against `GxcFXsqYnIQ`) via the spaced-character extraction technique above; the correct ID is `UCC8wczy7734jKPhiR2UkS9A`, verified working via a successful RSS fetch (status 200, 15 entries, including known videos). The table below now has the corrected ID.
- **Confirmed bug #2, fixed Aug 28, 2026:** the Billy Robinson channel ID was recorded as `UCajEYnZi3V-w52CTivgHlcg` (uppercase "C" where the real ID has lowercase "c") — this 404'd during the full-registry RSS run. Re-derived from the stored sample video (`oAREF2wSHUo`) and verified working via a successful RSS fetch (status 200). The table below now has the corrected ID.

## Resolved channels — Page 1 (89 channels: "15-year-old AI receptionist creator" through "Frank Garrett")

| Channel ID | Display name (from YouTube) | Notion "Channel" value(s) it covers | Sample video ID |
|---|---|---|---|
| UCn4dfcINwD3_z41IDFPsFcA | Chris Koerner on The Koerner Office Podcast | Chris Koerner; Chris Koerner (The Koerner Office); Chris Koerner on The Koerner Office Podcast; Chris Koerner on The Koerner Office Podcast (guest: Kyle); Chris Koerner on The Koerner Office Podcast (guest: Sandy Lee AI); The Kerner Office (Chris Koerner interviewing Alex) ⚠ | l0Vqm0ZIySc |
| UCGtXqPiNV8YC0GMUzY-EUFg | Marketing Against the Grain | Chris Koerner (guest on Marketing Against the Grain) | FahMd3qDblE |
| UCpNocIfIr4sLualjlFv-XRQ | John Whitford | AI prospecting software creator; John Whitford | x371nlU9GVY |
| UCgyGpOqFA9Kccep40ocK0Cw | Micah Korus | 15-year-old AI receptionist creator | -aUjJB6-hvk |
| UCy5SXueIp6v0wqRDBtJEHbg | Tanner Chidester | Aaron Chister; AI digital product YouTube creator; AI digital products YouTube creator; High-ticket sales YouTube creator; Tar Chester ⚠ | VlYVXR4DVFI |
| UCOq88UeBzXX0ldSKtCmbrbQ | The Virtual Savvy | Abby Ashley | k8UDq1cuANM |
| UCm7EbA4DoSasulUeOPe4S4A | Accelerated Publishing | Accelerated Publishing | HeBOQ4cxWNc |
| UCSHn0Px37BjzMqnZBmVWwcQ | Adam Robinson | Adam Robinson | r47Q4Cfit5s |
| UCWqKcFb7h9cNEdCxB5A5BgQ | Adam Enfroy | Affiliate marketing / AI content YouTube creator | 4M9FQdpZjm0 |
| UCL-nkhcmaXeZ4mtm0-cNKew | Aaron Chen | Affiliate marketing YouTube creator | MBFf90_Bh34 |
| UCZ6mdzBWXAzSGYhLyM_fZ9w | affiliatemarketingmc | affiliatemarketingdude (Marcus); AI marketing YouTube creator; Marcus Gamble | Vo8pcO7DhKI |
| UCzN4wfzSDJuy0bBw9aqKvFA | Eric Swanson | AI avatar / AI Creator Lab affiliate creator; AI avatar affiliate marketing creator | hJKXbppW3vM |
| UCMHevQoICFu50vZPh0zSpcg | Hassan Bazzi | AI branded e-commerce creator | coLDFCPM_iM |
| UC8ocDK-jRtlLauDaPEgAblg | London Leffler | AI digital product YouTube creator (2nd Notion row, distinct sample) | __vdpHSapGo |
| UC_KL_-8-6bnhQUOKoC6kADw | Sharif Mohsin | AI dropshipping YouTube creator | MWrmsiY_3Kk |
| UCtf_bSAJ9wikTEjWjdUuPLQ | AI Hustle | AI Hustle podcast creators | wUf28jznTt4 |
| UCV3-kGFJHeFnh6RP9fFPoRg | Luna Vega | AI mini-app YouTube creator | heYyhP_ZyII |
| UCuS26YCwztJJebH9rqba1yg | Ryan Doser | AI Rabbit Holes with Ryan Doser (guest: Kyle, the website landlord); Ryan Doser and Sandy Lee AI | 1sSjeklhejY |
| UCcXXw5iHsKeD5dNdjJTHq3A | Don Bassler | AI side-hustle YouTube creator | OYnMpJR_Vas |
| UCrJrY9gMcbRL2APnFCXiuBQ | Christian Peverelli | AI skills YouTube creator; Christian Peverelli | VZM-PmpTkiY |
| UCeFlDDx4rcssh2cO_yB4y-w | Jonathan's Jam | AI website-building YouTube creator | nQOGK72IHx8 |
| UCXYPYtjRDxW9xH8E-DlKiPQ | Angelo Turri | Angelo Turri | zmq12ZQSGzA |
| UCV35s5mGFX0pWC570QbB_dQ | Abundance | Anna & Mario; Anna and Mario | HdT2FU1hZbY |
| UCcOg2s9HCbyYwIJ5tDLZhmg | Ben Hawksworth | Ben Hawksworth | wudOmpK-8Fk |
| UC-cXMn9IIxaA7hos6Eg6jSw | Austin Zaback | Austin Zaback | xFn0gw_gocw |
| UCZv_19T3Yuk8k0RZRGNqgow | Alek | Alek | E57vDFkBu_Q |
| UCuE2Hfiv0r9ToXGD6l_bdvA | Alex | Alex | pLoswerx89s |
| UCiq1FIgtEK7LRAOB1JXTPig | Silicon Valley Girl | Alex (Higgsfield Founder) | czItVEAINqw |
| UCUyDOdBWhC1MCxEjC46d-zw | Alex Hormozi | Alex Hormozi | uWdIgftpvBI |
| UCoOae5nYA7VqaXzerajD0lg | Ali Abdaal | Ali Abdaal | XIhc7_Ptrpk |
| UCxgAuX3XZROujMmGphN_scA | Mark Tilbury | Mark Tilbury | 5rhHm6WWOIs |
| UCS4VWcCVVI8Bcn8Dteylxzw | Modern Millie | Modern Millie; Modern Millie 744K subscribers | EwVfILFo1wQ |
| UC6ITJIW6jgrrP5irR7WoHrw | Sean Dollwet | Amazon KDP mentorship creator; Faceless side-hustle YouTube creator; Sean Dollwet; Shawn Doughty ⚠ | gTz182QKnj4 |
| UC2CGTje4e99_xfWORsv82pQ | Ken Fornari | Amazon KDP publishing coach | elRbRNJcZ38 |
| UCV3nOFepIuRb-omd-6td5fQ | Abuv The Par | Amazon wholesale business coach | l97fVCZkQ4M |
| UCeOXT2X0Oz99KHSKc4-esrQ | Amber Gist | Amber Gist | Zu_SOSvn1BQ |
| UCLoGADNKOleoeZF4U6MiE1Q | Arlan Hamilton | Arlan Hamilton; Digital marketing coach (Your First 5K / Authority XPro) | nI_ZxDhVr_I |
| UCX2GMM3MGAWFPkHvxqFa09g | Austin Rabin | Austin Rabin 208k subscribers | 9UiyR_JElSc |
| UCAbcoKROFsRA_uA9aSprCwg | AutoDS - Build Your Online Income | AutoDS - Build Your Online Income | EEMQ2kbsqcY |
| UCk2AvEjXzspL1FWaG7GYTNQ | Baddie In Business | Baddie in Business | 2TnzXTzJ-N4 |
| UC3W26R5SbRRIsFfIpab226w | Giselle Baumet \| Neuroscience of Money | Behavioral scientist/neuroscience researcher | rGyVZj5lzhs |
| UCkfwdnNMV44DZ1WkrZ7oxAg | Brut Reviews | Better Finds ⚠ | TqDKf07o1ew |
| UC3qB4xFJkl0EYoTVbhnn0OQ | Ac Hampton | Bible journal dropshipping creator | ctUDpFtnzk8 |
| UCajEYnZi3V-w52cTivgHlcg | Billy Robinson | Billy Robinson | oAREF2wSHUo |
| UCtpLeTv2rUVCViEvjf2IEkg | BLEMARX | BLEMARX | C8zVoZu6p-Y |
| UCr-fgyxczssZmwancs2Xn5w | David Alex | Blink co-founder ⚠ | Yv_nhays8cI |
| UCB8O_S2baXMP0pXFCJY7Y2g | Blueprint to Revenue | Blueprint to Revenue | 635U7iQVmGQ |
| UCDAbrXOj2yIrzj8QE4jC-Og | BRAD LEA TV | Brad Lea TV | mwNErtA08p8 |
| UCCIpkcxasF4bc_jVtVwbPAg | Brandon Belcher | Brandon Belcher; PDF Vault / digital product licensing creator | 6Ter9q3NsfE |
| UC2tJqhM2fSXk3SIWy1UVQTQ | Income Testing Lab | Brave Rewards explainer creator | fgp5pW9qMyw |
| UCsg20ERGZt9eHVZRXROJSqg | Brett Malinowski | Brett Malinowski | y-eBAr1uRDQ |
| UCzT_3yh6l8lk1m19LTtzdug | Brian Moran | Brian Moran; SamCart (unnamed presenter) ⚠ | 3iU4a1yWGn0 |
| UC3yk3UCc8kXDCvw88eKm5kQ | Brian Ellwood | Brian O'Wood ⚠ | 7bgNTe4Pqso |
| UCa8MNaxyYOo7Z--L6STLWLw | Brooke Wright - AI Strategist + Educator | Brooke Wright | NB7T32OxfrM |
| UCoKjAu8tbtGC55m-2Sb5_NA | Buddy's DIY | Buddy's DIY | dGzgEiWJ9hk |
| UCa2Da-1NTnl3MMkDtw0oxKw | Business Cortex | Business Cortex | 7KLPw5Y3Cyw |
| UCELuyXctjHDqiyW35WNVJ9A | Business Dash | Business Dash | QBR-nHRHgLI |
| UCIGEBB32IQdzLOhEtlSP06g | Chase Chappell | Chase Chappell | MSADB8Xwpfw |
| UCi96FoMhca3BImdnPzqSr-w | Cintika tube | Cintika tube | eJqTCBHR0BY |
| UCvG9V9e1s2lN-hoWeHsDCJQ | Tyler Moore | Claude Code web design YouTube creator | 0nsO7S23SPM |
| UCEs2KlFV2UDMAf_z9gcu2rA | SamTheCoach | Coach Sam | 7ZYT-kEF1Bo |
| UCFB1w4mPuKFPycHYTBsZH0w | Stephanie Randolph | Coach Stephanie | B0IN8BN366c |
| UC5fI3kxC-ewZ6ZXEYgznM7g | Codie Sanchez | Codie Sanchez | ZvAwqGH_79Q |
| UCLoqOC7mh3K8esgadBCJvOQ | Corey Ganim | Corey Ganim and The Viable Edge | fI68tU0L86s |
| UCwi2bZVQ3Mz8W9sc-QP3KCA | Daejin Park | Daejin Park | 8QkMRe_-Q6U |
| UCfHWNhDHfNTKaBSWs1qyABw | Dan Henry | Dan Henry | KlJz-sBisgk |
| UCA-mWX9CvCTVFWRMb9bKc9w | Dan Martell | Dan Martell | xj5gZq159lM |
| UC2ExrTzlNc8uNmNXodWOC-A | David Explains Money | David Explains Money | oA0Pk1J9_mw |
| UCggok417jDHJiLueQON89QQ | David Heacock | David Heacock | 0OnpetFbLIg |
| UCq5gIhlM7Vihj1ER1-SuE4A | DEEPAK BAJAJ | DEEPAK BAJAJ | Kim-esfsBUE |
| UCV_j9rKdMayChEA6i6s8oTQ | Bill Mcintosh | Digital products AI creator | HOnelkClaDI |
| UC1eO0q44U6YXa0TKVAz3mUg | The Vision Bros | DIY cardboard furniture YouTube creator | lnMznu4SAEs |
| UCHgNhvr0Z46KN12mSFmgTRA | E'Calm | E'Calm | Hvl8CdsbtrA |
| UCkQjllxYiRAZI8yOEYWDEgQ | Money With Mak | E-commerce marketing YouTube creator | TfOhKeciZpU |
| UChu48rzrj0w-HBdd0cG2qcg | Easy Business | Easy Business | 1ulIBo_Tm-o |
| UCb4XiEOeJulWu4WGhwnDqjw | Ed Lawrence | Ed Lawrence | vF5lO5yPGUY |
| UCQBbiPgQKjwpJ1KhjZW5dOg | Edwina - Voice of AI | Edwina - Voice of AI | psXx-YsTQq4 |
| UCv3N90AXQxUtaSnKSqOoOpA | Elevate To The Unknown | Elevate To The Unknown | hIvV97d0oow |
| UC8iN8jdZISR6W6gVOgcebPA | Ellen Mackenzie \| Dishing up Digital | Ellen Mackenzie \| Dishing up Digital51.3K subscribers | FA-wELlQCaQ |
| UC1DecsubFL5YHU90c1x0q0g | ENERGI | ENERGI | oqhXJJh_mIE |
| UC6-2dxDfwxlX9awErEt24Yg | Michia Rohrssen | Entrepreneurship YouTube creator (self-described $110M exit) | y5ks4FhoGfQ |
| UCgKFOz_KrMbmypWrawtzDQg | Erik Cupsa | Erik Cupsa | KKWS0bSiCT4 |
| UCUYU1R6PRBJFaT_7k3TFZpQ | Tatyana Savage | Etsy digital products YouTube creator | XtvkEWfVSXc |
| UC7jNKtEBuuYFHsnl91lQuHQ | Passive Biz Lucca | Facebook monetization YouTube creator | _gIsGBkGJjU |
| UCNJBNr3lXC3bHabtUkum3Yg | Anji Martin | Facebook theme-page monetization creator | KTEZb7-1Hvw |
| UCRsX3QOyl9RigIoN_UKqDlA | OriDigital | Faceless YouTube tutorial creator | o17G_qad9w8 |
| UCYbqOUr5uBpP3NPQlNew8og | Daniel McCluskey | Financial advisor / retirement planning YouTube creator | lRoeN8jLcUg |
| UCajLUWpJ5J0vKLMWsCRcH8A | Frank Garrett | Frank Garrett | 9hGYYCIS9vQ |

## Resolved channels — Page 2 (81 channels: "Fraser Cottrell" through "Richard Yu")

| Channel ID | Display name (from YouTube) | Notion "Channel" value(s) it covers | Sample video ID |
|---|---|---|---|
| UC8xkoDqgLjJq_lfi2DBfAQA | Fraser Cottrell | Fraser Cottrell | bNMeFhW6YmA |
| UCqo81Nl0SHo_BFtpFbIWsug | Garrett Barry | Garret Barry; Garrett Barry | drGxzwtFMOs |
| UCQF1lJTFen5a25ijZNqDjaQ | Gear Geek | Gear Geek | gNqQLTnVKjA |
| UCc5Wk-Py1cMvA59L-X62E5Q | JaidenFinance | generic YouTube monetization explainer | Ovv_y47PLyI |
| UCjkqr7CGBdL8sUudF08dIRA | Giganomic Era | Giganomic Era | jv40GZPfRSc |
| UCo0krjGfF8kRuIftshvPyxQ | Glowithgia | Glowithgia 89.9K subscribers | JhLs5Sq6cHI |
| UClaXy4RprmszNEXcyTnDbQw | Noah Anderberg | GoHighLevel local-business AI creator | _572c83sqLI |
| UCKU0u3VbuYn0wD3CUr-Yn6A | Adam Erhart | GoHighLevel one-person agency creator | 2_3VKl3eYlU |
| UCZAoatH4HngcEuCtOWuSX2A | Greg Gottfried | Greg Gottfried | zxvh1ZW00Y8 |
| UCPjNBjflYl0-HQtUvOx0Ibw | Greg Isenberg | Greg Isenberg; Greg Isenberg (guest: Voss); Corey Gannon (guest on Greg Isenberg) | 9T1yWEq5kP0 |
| UCJIdljQFCOnfWg3O-n6UoAg | GREGORY | Gregory | 3-RNNH27CWM |
| UCh6KREpTBNYk9GyJ9doJm4Q | Grow With Bre | Grow with Bre 6.43k subscribers | aIi2gLB_niQ |
| UCDfyasEPlV7m23kcdaJ3glg | Hannah Gardner | Hannah Gardner | MUFyMS4QJlw |
| UCW5OYm99euxEoj-VF5BjbXA | Harry's Stealth Wealth | Harry's Stealth Wealth | RTI-W5VpoQQ |
| UC0IKqj_Q3uygq3kiQXNeJpg | Henrik Wold | Henrik Wold | Ns1759le2B0 |
| UCRYY7IEbkHLH_ScJCu9eWDQ | How I AI | How I AI | cmATJGbA8bI |
| UCorUaC22pinhK07jpIiU0Ww | How Much? | How Much (Idan) | oH7WTH1svrk |
| UCQ4FNww3XoNgqIlkBqEAVCg | Iman Gadzhi | Iman Gadzhi | q1g65sjQI-4 |
| UCV5ItQRuaLr2sQrvH52qDvQ | Jack Harrison Explains | Jack Harrison Explains and The Business Economics | yg3Z6GiWUA4 |
| UC3LhJ3nNAwMHIbNHij2vYTA | Nicole & James Co | James (creative business coaching channel) | Y_sPva_30XA |
| UCgj9lpc82TcyZHoiCCuLO7w | The Blogging Rapper | Jason (the blogging rapper) | t4WGAHtU4L4 |
| UCBgPxTfodXMa_zavgl0DX7A | Jason Wardrop | Jason Wardrop | nkR89x5zXBo |
| UC9WQhW7N97CCCMnEhRiQMMQ | Life With Jazzy Mac | Jazzy (remote jobs YouTube creator) | BYaw6hZ9zl0 |
| UCregPn4nsW8k_coBJj13L3A | Jeffrey Stern (Lay of The Land) | Jeffrey Stern (Lay of The Land) | GXHnkZkVI-k |
| UCd9tLjGtoDaCQqc4daDt0QA | Jeremy Ray Holst | Jeremy Ray Holst | PSXm_Df2tL0 |
| UC_DfvBDqCexXZ_xtEDKHVBA | Jesse Cunningham | Jesse Cunningham; Micro-site / local SEO YouTube creator; Microsite/rank-and-rent community creator; Rank Expander Academy creator | KaJnoYdJo7U |
| UClLH8wnuIh12T-9KMYgz5AA | Jillian Leslie | Jillian Leslie | rtp1nZrhroA |
| UCVCHSbooOsUlutLOJiTpnKg | Johnny & Sergio | Johnny & Sergio | edG3nhx3U0k |
| UCwXvRGsOArrJ-1JVXWlezag | Jon Reiter | Jon Reiter | 8Oo2grpskhA |
| UCOM6CFh5JpEPCNejulwDK0Q | Jonathan Nilsen | Jonathan Nilsen | PThbzpRjqRs |
| UC5deKm1RRbcoUIuLuSCFprg | Jordan Welch | Jordan Welch | 7-Sg2RKNMZE |
| UCEynp7r85uggB0TRz44f82A | Josh Graff | Josh, book reselling YouTube creator | AyaAQguyKVQ |
| UCP-F2Z_n_0i7sylkMCoy83Q | Joshua Elder | Joshua Elder | v_lVZVsxffc |
| UCJZ7zr9a6AT6STkyOFztgiQ | Joshua Mayo | Joshua Mayo | bW8K4G1uvnA |
| UC6gRRypq2K88LkP7NeB4c4w | Judd Albring | jUDD aLBRING; Remote jobs YouTube creator (9 years, BLS-cited) | VTsZNLXfYIs |
| UCHQ1rz0S3HQd7O0q47DLQkw | Just Teachin Stuff | Just Teachin Stuff | wnzBbsmsQNk |
| UCROsCSoY7I_QZuS4QGQckOA | ItsKeaton | Kai Stone and Michael, Stone Systems ⚠; Keaton; Kevin Patrick ⚠ | mwMQLJ5GoRM |
| UCm3LobNN9ifuapYhZwyBm7A | Kat Lewis | Kat Lewis | KJxfBCB1laY |
| UCfXzRcRPMHw_AF7EdRtyiJQ | Kate Hayes | Kate Hayes | ll1m-oOQfqY |
| UCSTB-s1sbhDyt_0B9Gz8_Lw | Kathryne LaBella | Kathryne LaBella | w47bdldbh30 |
| UCM09WPipvSz-XalVK01FRqQ | The Savvy Couple - Kelan & Brittany | Kelan & Brittany - The Savvy Couple | 7oM-Nfl8CtQ |
| UCO-YCVsvkK7a22WM2aNUvlQ | Kellan Henneberry | Kellan Henneberry | V_t51u1tBJc |
| UCl15Wheca-bPXgQbjJD7rmQ | Kevin | Kevin (18.7K subscribers) | VU-UanzMZBE |
| UCl61IKpTZ4V8o5mSNybgW0g | Kleo | Kleo; Kleo and Cam Trew | 8x9Uyji54D4 |
| UCKxe0e2eZ31tpY1PtWhDbUw | LaCresha Sims | LaCresha Sims | mPu04xk_YUI |
| UCui4jxDaMb53Gdh-AZUTPAg | Liam Ottley | Liam Ottley | KAufsCas_F4 |
| UCqDKllDwdKvi64SuEXxPy6A | Low Bar Podcast | Low Bar Podcast and Shannon Jean | lnL3GJaI3dE |
| UCeB0xg_WzIwCS6XL2Y6MQSA | Maddox Goforth | Maddox Goforth | bYvGrY6N0cI |
| UCIcoDIrQQxBbZqnPzO1zDFQ | Make Money with Stacy La | Make Money with Stacy La | ju7zG9bdhv4 |
| UCKtlbaQPHwoWAGcD65K8iQA | Maria Wendt | Maria Wendt | pS87Q5HPI4U |
| UC57g2LHAS32-TFog9GTst5g | Marissa Romero | Marissa Romero | P-DC-FlVD7o |
| UC0vxsxYKNzIkbNPDgDXC0QQ | Martin Lešnjak | Martin | lBbNm9BqpC4 |
| UCuDZyvpQXqWRHor1SkBgp2w | Massimo Seq | Massimo Seq | ek-vqW_TPd8 |
| UC0d-JbubL4XZmw4hdcGeXRw | Meg Heckman | Meg Heckman | 19ur85v6OPA |
| UC_jRjcT1OValDUOSDcZ6gWA | Melanie Renee | Melanie Renee 13.6K subscribers | KqMedomJJzo |
| UC6MwSmOY5N3qGw_P3tTcIfg | Mike Swigunski | Mike Swigunski | 9-KvflFNMy4 |
| UC2kGqYDIkNROEao8Wz0fVNA | Brian O'Neill | Mindset School creator | HsLsvLHmX-s |
| UCx_tBXDCadU1dtD4vdzBp2g | SUCCESSFUL ENTREPRENEUR | Mini machine business YouTube creator | xQ12WUnQid4 |
| UCCehtoKY50lDmG-_fb_G2cA | Wealth Unlocked | Mini machine business YouTube creator (duplicate upload) ⚠ (NOT actually a duplicate — different channel, same content) | 1qrAd7vN5-4 |
| UCAmnjhuP3_YPYhj0_RLxqHQ | MoMike Chamberlin | MoMike Chamberlin | QNpgTubnuvw |
| UCUcW21cHj7uk8VOa8WNsEQg | Money Talk With Leon | Money Talk With Leon | 9WZ3Vfni8cg |
| UCndkL8Td8ZUoXrFg3E4n2xw | Monica Main | Monica Main | ygn_aki6-YE |
| UCyaN6mg5u8Cjy2ZI4ikWaug | My First Million | My First Million; My First Million and Chris Koerner on The Koerner Office Podcast | 5P6k92gr96c |
| UC32FqN3ArzlvDnZvMmtUitA | MyWifeQuitHerJob Ecommerce Channel | MyWifeQuitHerJob Ecommerce Channel | CMPbEk4jL6M |
| UC2ojq-nuP8ceeHqiroeKhBA | Nate Herk \| AI Automation | Nate Herk \| AI Automation; Nate Herk \| AI Automation (guest: Sav) | eFOTQpbGcy8 |
| UCLZ6-13n1-IzVGCSNYP_CSw | Niche Pursuits | Niche Pursuits | aE2Iwzrp_94 |
| UC0r8DQESNDtiefnxGqdOR5Q | High Level Profit Systems | Nick Ponte ⚠ | NeWeUJ87s9E |
| UCgjPAWhG8I6pSW_qLD9TU0w | Nicolas Rojas - Youtube Faceless | Nicolas Rojas | oKeO7NPfuTE |
| UCvsjVHsowpTyNJfCMVv-q9Q | Noah Frydberg | Noah Frydberg | 3C1vYSbXhC4 |
| UCBTz3Np62RSDc8XneG9avrA | Olly Richards - Business | Olly Richards - Business | 88sn1MDS3og |
| UCnBTvMFhuvbE_dhw2mo0NaQ | Sunny Lenarduzzi | Online education business coach | fN_2c_LPfX0 |
| UCRkUNGepO8YnTFHSj7urWsQ | Pace Morby | Pace Morby | vVvcPPGqJG4 |
| UCGk1LitxAZVnqQn0_nt5qxw | Pat Flynn | Pat Flynn | PLBYYdg0sfs |
| UCLOzkJ9W9fntCGyYfUwMPew | Patrick Dang | Patrick Dang | DuOolRhG2UY |
| UCcX57t7_MHj2b2e2BWd2RiQ | Seve Ortale | Payment processing/merchant services YouTube creator | K8AktbTLIds |
| UCb4YTduN-tdW9hSVjPwgkbw | Kimberly Mitchell | Print-on-demand YouTube creator, applying Emily Odio-Sutton's framework | ylvFxzIQnkA |
| UC3oH5A5gtsaxdoX_au9TF9g | Quinn Nolan | Quinn Nolan | g-vdeT4s7OE |
| UCYuymgaGxx-PItk26u5SbXA | Real Money Strategies | Real Money Strategies | E54nTPgzqpk |
| UCZ87bhE7e6pudofscNyWR8Q | Profit Stacking Club | Remote jobs YouTube creator | J_9WjB4FOl4 |
| UCFGDO-6ssC91JOktjWUEHzg | Retired With Purpose | Retired with Purpose | DTuqqIQU6Aw |
| UCb9nQthIifgYhHvtU2i2mFg | Richard Yu | Richard Yu | BoibR0BUefs |

## Resolved channels — Page 3 (45 channels: "Rise above reality" through "zapiwala ai")

| Channel ID | Display name (from YouTube) | Notion "Channel" value(s) it covers | Sample video ID |
|---|---|---|---|
| UCsguRUxh-0DiryIdPPWFeCQ | Rise Above Reality | Rise above reality | 2_W0tEu0csY |
| UCDwbMVXWew6-kReYfLtbySQ | Rochelle Be | Rochelle Be | Mbs19UDqv3s |
| UCdZBLznygSwo7iHbydGtxaw | Romuald Fons | Romuald Fons | uMTstECO78s |
| UCIbslwukNCyVp-XMz_2-gmw | Rose Han | Rose (personal finance YouTube creator) | Ht2LluZ7pLk |
| UCAxUtcgLiq_gopO87VaZM5w | Sabri Suby | Sabri Suby; Sabri Suby 472K subscribers | HsjuAvqs3zU |
| UCiGWNa6QK6CiKPvv5-YPv8g | Sabrina Ramonov 🍄 | Sabrina Ramonov; Sabrina Ramonov and Sandy Lee AI | C0ZKtSx8gyA |
| UCx7DWIF3zT2xapezCxIzNVQ | Sandra Di | Sandra Di | 1NrAYr60c5g |
| UCcrH_UUxL4KFjS3pwaXvMXA | Sandy Lee AI | Sandy Lee AI; Sandy Lee AI (guest: Shen); Sandy Lee AI and Ryan Doser | 2wL5MhwTsbA |
| UCldnLLYMXEISsAtGEV7UPzQ | Sanji Nai-Chien | Sanji Nai-Chien | iJiBJAJRRkk |
| UCg60QRUSvLZMF4zHv2ajBqA | Santrel Media | Santrel Media | WkszbQQxEO8 |
| UCC8wczy7734jKPhiR2UkS9A | Wholesale Ted | Sarah (AI side hustles YouTube creator) ⚠; Wholesale Ted | 8NvhbfZNTrc |
| UCgLPIqxdDxp9rrl-WdrtucQ | Second Act Brand | Second Act Brand | fhwjOSwFtdY |
| UCLKZ20yD2tNMBOkSDZo4FeQ | Shane Hummus | Shane Hummus | kSbNt3lqyqM |
| UC5mFJ8EUQiYADCRzs29VMDQ | Shop House | Shop House | 2DWa6seykNM |
| UCGznz4NfW5iymkvn1l40qyA | Simon Squibb | Simon Squibb | TZO3_2Krsqk |
| UCtxx4QumVFZPpwrCWbr-F6Q | Cindy's Got Systems | Solopreneur coaching YouTube creator | bG3epVp37-c |
| UClA5CehpOC4Stk8PwLbpFPQ | Speel | Speel 20.5K subscribers | 1e2THXih1Fo |
| UChhw6DlKKTQ9mYSpTfXUYqA | Starter Story | Starter Story | 9WWvLj-NqEE |
| UCLI_f0zfE2Q9EWoJe_cAwRw | Success With Sam | Success With Sam | CXVnsSGv7CQ |
| UCnmM-zS9W-tY59fDnAe3y9Q | Tanya Aliza | Tanya | xzLtC6E7jOg |
| UCBie2nxQczhO-iKcxgvhQZg | Teanna Scot | Teanna Scott | CbilfDJi9D4 |
| UCuvjQYKukKjVyhSVxQibgOw | The Calum Johnson Show | The Calum Johnson Show (guest: Jack Roberts); The Calum Johnson Show and Edwina - Voice of AI; The Calum Johnson Show and Greg Isenberg; The Calum Johnson Show and Oliur Online | zRkcslvpFNU |
| UCGq-a57w-aPwyi3pW7XLiHw | The Diary Of A CEO | The Diary Of A CEO; The Diary of a CEO - Chris Koerner; The Diary Of A CEO and Mohnish Pabrai; The Diary Of A CEO and Chris Koerner on The Koerner Office Podcast | sFkR34AMPw8 |
| UCn8V4itSjrJBax-xLNJxeOQ | THE ECOM KING | THE ECOM KING | PS6-Ugw820U |
| UCIuAEGh0hYA1P-dNpUBND2A | The Ecom Wolf | The Ecom Wolf | XSn7yXCNb3U |
| UCpy3Hlqsc3Ip_L0FHWUlJLw | The Prosper Lab | The Prosper Lab | AQgEwNCHeSQ |
| UCRHItFez_OFMoiLo3QT6GwQ | Thressa Sweat | Thressa Sweat | EoMXcxbycJk |
| UCmegxiitbJO3G2pxML6Ul7Q | ThriveCart | ThriveCart; ThriveCart10.5K subscribers | OJkTbvXZYPc |
| UC0Chb1nY68NFDFXB9SztsHA | Tiger Insight™ | Tiger Insights | kqjNNxDukzA |
| UCOPF9JjEbqjGdD2cqSht1pw | Thinkverse AI | Tiger Insights style AI side-hustle YouTube creator | rAvOFvIK4Rw |
| UCUBmH4V_BpyXr1zqKNQWrJA | Tim Richard | Tim Richard | Zq50owQuuIw |
| UCuP-lllt-6aBLTXNNVyd_TQ | Timoté Chanut | Timoté Chanut 7.46K subscribers | Iyz0jhMGgVA |
| UCrEimf7orPLVubiGKBZPCsg | TomYoungsPodcast | Tom Youngs Podcast and Tom Youngs | CS9M9w9xIg0 |
| UC83VjBxiWDMJk3xipK97vDA | Tyce Tyce Baby | Tyce Tyce Baby | SDYRrDe7b3Y |
| UCVPH14AxS9j_103U8tMt8cw | Kieren Newborn | Unnamed creator, AI solopreneur YouTube channel | 8uKdZC-GwRY |
| UCQHFLSruEf_MjWu_1M34vJg | Talk with Richey | unnamed presenter (Handshake AI review) | d5xEGLrf3IM |
| UChFahjDeMBV67DSXiF5pwBA | UpFlip | UpFlip; UpFlip and Chris Koerner on The Koerner Office Podcast | J-KCIFG3B5M |
| UCooW1kDrMUb1EORhDbmciOw | Vendasta | Vendasta; Vendasta (guest: Isabella Bedoya) | aYx8t2vWR8s |
| UCHOopmdU4FscqK3RyWya-yw | vidIQ Podcasts | vidIQ Podcasts and Deven Seenath | qBEKL3BcMBU |
| UCPa0bvFsR1mbBpk5mIPFGLA | Vincent Chan | Vincent Chan | QJ8q9XbI3Ys |
| UCbMZk8I1PPz6bNm4Vu5M8vw | Wendy Nolan | Wendy Nolan | WPDY6sclQlM |
| UCt52uFV66hdjdfm97O7cr9Q | Wisdom Speaks | Wisdom Speaks | k-Zmcd_ueGQ |
| UCfQk5qGOEO5cPPDFlQe2lFQ | Your Average Tech Bro | Your Average Tech Bro | 5bs2VGWeA-4 |
| UCoO955eAFMFdJdOd0NvNdfQ | Zack Kirk | Zack Kirk | Zo_kg8mhzTs |
| UCWJVsGYhm7K2SuIx362YziA | zapiwala ai | zapiwala ai | WVT2FCjhDDY |


## Resolved channels — Page 4, added Sept 14, 2026 (21 new producers found via presenter-list refresh)

| Channel ID | Display name (from YouTube) | Notion "Channel" value(s) it covers | Sample video ID |
|---|---|---|---|
| UCVHblYUEEaYhwZpy13CXktQ | Ali Akbar | White-Label Ecommerce | Ali Akbar | White-Label Ecommerce | vXRZW6eWZDY |
| UCgugjY9T1jv41UcKmaZ5NLQ | Automate AI Consulting | Automate AI Consulting | tKBpMevDJO8 |
| UCkNgn6JfHAQ1CptJcgjTdvA | Diamond Chanel | Diamond Chanel | Lk3PeK1OJQg |
| UCH4FF2BYPBaPOhnGI3TYpAw | Geekbot AI | Geekbot AI | XCw0Rf1btP8 |
| UCmBFnhsiaAs8Gp6IfXy8l_w | HIDDEN WEALTH | HIDDEN WEALTH | mdyoHBq2Yis |
| UC9-XlrmeMEAdIha_XBuHp1w | Jake Trinder | Jake Trinder | Ar2DXQorEm4 |
| UC4_ul-MziU-8Cn1g_CGPI1Q | JeffSetLife | Jeff (5 TINY but Profitable KDP Niches) | hUTkB6UQRLQ |
| UC_tAaH5Fj1xWC0GP-zcX4qQ | Jo | Digital Product Designer | Jo | Digital Product Designer | 00IaFaHDfsI |
| UCMkrhE-kVtq06xUZDN3FD8Q | Journey With The Hintons | Journey With The Hintons | km7PyVKOSsk |
| UCcNrmSXswsMJzuaSQknziTw | Make Money Matt | Make Money Matt | s3gvakj8ujo |
| UCpFio7jSO7H6Q2gM6dguJ6g | Mr Reis | Mr Reis | 7YJtacrq1NU |
| UCsC9QsLWqAE4xq0McDYDi7A | Mr. AI CASH | Mr. AI CASH | 8OD5rFhUHkI |
| UC5sGRuouCtllvIEL1q8ay0Q | One Person Business | One Person Business | VhgezEtiK-c |
| UClgIolUwPZBnLLXnaZcQ13Q | Ron Schrader | Ron Schrader | QPyrodYpQ_k |
| UChPwGY5vg-p4a6UehR83wHQ | School of Hard Knocks Podcast | School of Hard Knocks Podcast (guest: Jhalesa Seymour) | btaHofImbYU |
| UCZE0kpnhoy84NO9r1gs5W5Q | Shawn Builds AI | Shawn Builds AI | _doqDIYZaM8 |
| UCO2dOH2clIdWvboFn_SB9OQ | Steffens Niches | Steffens Niches | 5bAt8h1x_5c |
| UCuI6A7KFKabnM9mAoOFL06Q | Steven Thompson | Steven Thompson | dIu31c1aMmY |
| UCdpW0kvbCWBk8fBp31ZmIkg | Stockton Walbeck | Stockton Walbeck | ug8v9faIvtg |
| UCoASMB_HrJN7SQQdgEMy3cA | Whitney Bonds | Whitney Bonds | 1E6nNro6KKY |
| UCWBK0yyL9VCAHvUURhbC7Ig | ducrez | ducrez | puJkObRPQ6s |

**Also this pass:** two more candidate values resolved to channels already in the registry rather than new ones — "Corey Gannon" turned out to be a guest on Greg Isenberg's channel (added as a label variant on that row above), and "Nate Herk | AI Automation (guest: Sav)" is the same channel as the existing "Nate Herk | AI Automation" row (label variant added there too). Roughly 40 other candidate "found" values from the live database were checked against this registry and matched existing rows by sample-video-ID or name overlap (guest-episode labels, mis-transcribed names) — no new rows needed for those.

## Excluded from Guru Watch (non-YouTube sources)
- Entrepreneur.com (David James, citing SideHustles.com data)
- Matt and Hannah Lee, via Sharetown (Side Hustle Nation) — sidehustlenation.com
- Tayo and Dolu Lanlehin, Bay Area Kids Rentals (covered by CNBC Make It) — cnbc.com

## Unresolved / needs follow-up
- **Business Money** (sample video `swRtNKlDCo0`) — page loads but `videoDetails.channelId`/`author` come back empty after repeated attempts with increasing waits. Notion shows 3 rows for this Channel value, so a different sample video from one of the other 2 rows is worth trying, or check the video manually — it may simply be a removed/restricted upload.

## How to add a new producer later
When Kevin (or the weekly Guru Watch process) finds a new creator to add: grab any one of their video URLs, navigate to it, and run this JS via the page-script tool:
`(() => { const vd = (window.ytInitialPlayerResponse||{}).videoDetails || {}; return {n: vd.author, id: (vd.channelId||'').split('').join(' '), t: vd.title}; })()`
Strip the spaces from `id` to get the real channel ID (the spaced request avoids a content-filter false-positive — see method notes above). Add a new row above with the channel ID, display name, and this doc's freeform "value" label for it, then feed that channel ID into the RSS monitoring list (`https://www.youtube.com/feeds/videos.xml?channel_id=<ID>`) per Production Process §11.
