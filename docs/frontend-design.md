# Frontend UI conventions

The app uses a shared white theme, native controls, and the existing React UI primitives. No UI library or icon
package is needed.

| File | Responsibility |
| --- | --- |
| `src/frontend/src/theme.css` | All literal colors, semantic accents, shared control heights, typography, spacing, and panel dimensions |
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
