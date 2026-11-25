# Frontend UI conventions

The app uses shared light and dark themes, native controls, and the existing React UI primitives. No UI library or
icon package is needed. The first visit follows the operating-system color preference; the sidebar and login-page
toggle save an explicit choice in local storage.

| File | Responsibility |
| --- | --- |
| `src/frontend/src/theme.css` | All literal light/dark colors, semantic accents, shared control heights, typography, spacing, and panel dimensions |
| `src/frontend/src/theme.tsx` | Persistent theme state and the shared theme toggle |
| `src/frontend/src/styles.css` | Component appearance and layout using theme variables |
| `src/frontend/src/ui.tsx` | Shared behavior: fields, ratings, switches, segmented choices, tabs, dialogs, tags, and callouts |
| `src/frontend/src/icons.ts` | Named icon glyphs, assignment status icons, and the module-to-icon mapping |

`main.tsx` imports the theme before component styles. Update theme variables to change the app's color scheme;
do not add hex/RGB colors or private palettes to pages. Default panels, cards, buttons, inputs, and selects are
white. Selected states use the shared blue accent. Status tags, warnings, and revision additions/removals use
explicit semantic colors from the theme.

Use `Field` for a labeled native input, select, or textarea. It associates the label with the control automatically
and supports an optional help message. Controls use `.input`, `.select`, or `.textarea`, which share borders,
focus rings, disabled styles, and a 36px base height. Use `.control-compact` for table controls and `.control-number`
for a narrow numeric input. Long writing prompts may explicitly request more textarea rows.

```tsx
<Field label="Title" hint="Shown to students.">
  <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
</Field>
```

Use `RatingScale` for every five-point question. Questionnaire confidence/experience and instructor feedback
helpfulness share the same 36px options, endpoints, selection styling, disabled state, and native radio keyboard
behavior. Keep each question's label and endpoint wording appropriate to its purpose.

```tsx
<RatingScale label="How helpful was this?" value={rating} onChange={setRating}
  low="Not helpful" high="Very helpful" disabled={saving} />
```

Use `.btn` for normal actions and `.btn.sm` for a deliberate compact action. Use `.form-actions` to align a group
of form actions and `Modal` for shared dialog sizing. Keep layout-specific widths and dynamic progress values
local; keep reusable visual rules in the shared CSS.

Import icons rather than embedding glyphs in pages. Add new icons and module mappings in `icons.ts`:

```tsx
import { icons, moduleIcon } from "../../icons";

<PageHeader icon={icons.assignment} title="Assignment" />
```

The registry keeps the existing emoji icon style; a future icon-style change can be made from one source.

The configuration editor is shared by course defaults, assignment overrides, experiment conditions, and per-student
overrides. It uses the same white panels, form labels, help text, input heights, selection colors, and compact reset
buttons. Control and label widths come from `--setting-control-width` and `--setting-label-width`. Rows stack based
on the editor's own available width, including inside a dialog or experiment condition. Setting labels and help
are associated with their controls; segmented choices and multi-select options expose their selected state.
