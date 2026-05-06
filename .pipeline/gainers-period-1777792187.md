# RESEARCHER FINDINGS

## Root Cause

**The period buttons DO work — but there are TWO separate "En Çok Kazandıranlar" sections on the same page, and the user is likely interacting with the wrong one.**

### Evidence

**GainersSection appears only once in the codebase** (FunLists.tsx line 79). However, `HomePageClient` also renders its own gainers/performers UI in the "Tüm Varlıklar" section (lines 459-493) which has period buttons (1G, 1H, 1A, 3A, 6A) that use `mixedSortKey` — a completely separate state mechanism.

### The Two Sections

1. **GainersSection** (in `FunLists` → `CategorySection`):
   - Uses `period` state (`"1G" | "1H" | "1A" | "3A" | "6A"`)
   - Sorts `mixedItems` via `getReturn(entry, period)` in `useMemo`
   - Dependency array correctly includes `period`
   - Column header shows period label dynamically (line 204)
   - "Tümünü gör →" link goes to `/performers`

2. **"Tüm Varlıklar" tab bar** (in `HomePageClient`, lines 432-500):
   - Has its own period buttons (1G, 1H, 1A, 3A, 6A)
   - Uses `mixedSortKey` state (`"daily_change" | "weekly" | "monthly" | "quarterly" | "bi_annual"`)
   - Different `useMemo` (line 207) that sorts by `mixedSortKey`
   - This is the section users are likely clicking, not GainersSection

### Why the User Sees the Bug

When a user clicks period buttons in what appears to be the "En Çok Kazandıranlar" section near the top of the homepage, they are actually clicking the period buttons in the **"Tüm Varlıklar" section** (the big tabbed grid below). The active button updates (because `mixedSortKey` state changes), but the GainersSection at the top — which uses a separate `period` state — doesn't change.

### Additional Note on GainersSection Itself

The code inside GainersSection is correct:
- `useState<Period>("1A")` at line 93
- `useMemo` with `period` in dependency array at line 141
- `setPeriod` using `const k = p` pattern at line 168 (Terser fix applied)
- Column header reflects `period` at line 204

The component itself has no bugs — the confusion is from having two visually-similar period button groups on the same page.

## Files Analyzed

- `gainers-section.tsx` — component logic is correct; period state, useMemo, and button handlers all work as intended
- `FunLists.tsx` — renders GainersSection once with correct props
- `category-section.tsx` — passes `turkishGainers` through to FunLists (no GainersSection here)
- `HomePageClient.tsx` — has a SECOND independent period-button group for the "Tüm Varlıklar" tab; this is NOT GainersSection but shares visual design language

## Recommendation

The period buttons in the "Tüm Varlıklar" section work correctly for that section's list. The issue is purely UX confusion from two similar-looking controls on the same page. If the fix needed is to make the GainersSection at the top respond to period clicks, that code is already correct — the user may need to be educated on which buttons control which section, or the visual design should be differentiated.
